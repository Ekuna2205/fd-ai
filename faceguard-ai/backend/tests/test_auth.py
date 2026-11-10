from datetime import UTC, datetime, timedelta

import jwt
from sqlalchemy import select

from app.core import security
from app.core.config import get_settings
from app.models.system import AuditLog
from app.models.user import User
from tests.conftest import PASSWORD, headers, register


def test_first_user_is_administrator_next_is_viewer(client):
    first = register(client)
    assert first.status_code == 201
    body = first.json()
    assert body["token_type"] == "bearer" and body["expires_in"] > 0
    assert body["user"]["role"] == "administrator"
    assert "password" not in str(body).lower().replace("password_hash", "")
    second = register(client, "second@example.com", "Sam Second")
    assert second.json()["user"]["role"] == "viewer"


def test_register_never_accepts_a_role_from_the_client(client, admin):
    r = client.post("/api/auth/register", json={"email": "sneaky@example.com", "full_name": "Sly Fox",
                                                "password": PASSWORD, "role": "administrator"})
    assert r.status_code == 201 and r.json()["user"]["role"] == "viewer"


def test_password_is_stored_as_argon2_hash(client, db):
    register(client)
    user = db.scalar(select(User))
    assert user.password_hash.startswith("$argon2id$") and PASSWORD not in user.password_hash


def test_duplicate_email_conflicts_case_insensitively(client):
    register(client, "Ada@Example.com")
    r = register(client, "ada@example.COM")
    assert r.status_code == 409 and "already exists" in r.json()["detail"]


def test_validation_errors_are_field_level(client):
    r = client.post("/api/auth/register", json={"email": "not-an-email", "full_name": "A", "password": "short"})
    assert r.status_code == 422
    body = r.json()
    assert isinstance(body["detail"], str)
    fields = {e["field"] for e in body["errors"]}
    assert {"email", "full_name", "password"} <= fields


def test_password_needs_letter_and_digit(client):
    r = register(client, password="onlyletterslong")
    assert r.status_code == 422 and r.json()["errors"][0]["field"] == "password"


def test_login_success_and_last_login_set(client, db):
    register(client)
    r = client.post("/api/auth/login", json={"email": "ADMIN@example.com", "password": PASSWORD})
    assert r.status_code == 200 and r.json()["access_token"]
    assert db.scalar(select(User)).last_login_at is not None


def test_login_failures_are_generic(client):
    register(client)
    wrong = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "Wrong-password-1"})
    unknown = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": PASSWORD})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json() == {"detail": "Incorrect email or password."}
    assert wrong.headers["www-authenticate"] == "Bearer"


def test_disabled_account_cannot_log_in(client, admin, viewer, db):
    client.patch(f"/api/users/{viewer['user']['id']}", json={"is_active": False}, headers=admin["h"])
    r = client.post("/api/auth/login", json={"email": "viewer@example.com", "password": PASSWORD})
    assert r.status_code == 403


def test_me_requires_valid_token(client, admin):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers=headers("garbage")).status_code == 401
    r = client.get("/api/auth/me", headers=admin["h"])
    assert r.status_code == 200 and r.json()["email"] == "admin@example.com"


def test_expired_token_is_rejected(client, admin):
    s = get_settings()
    past = datetime.now(UTC) - timedelta(minutes=5)
    token = jwt.encode({"sub": admin["user"]["id"], "jti": "x", "iat": past - timedelta(hours=1), "exp": past,
                        "iss": security.ISSUER}, s.jwt_secret, algorithm="HS256")
    r = client.get("/api/auth/me", headers=headers(token))
    assert r.status_code == 401 and "expired" in r.json()["detail"]


def test_logout_revokes_the_token_server_side(client, admin):
    assert client.post("/api/auth/logout", headers=admin["h"]).status_code == 204
    assert client.get("/api/auth/me", headers=admin["h"]).status_code == 401
    # a new login still works and yields a fresh, valid token
    t = client.post("/api/auth/login", json={"email": "admin@example.com", "password": PASSWORD}).json()["access_token"]
    assert client.get("/api/auth/me", headers=headers(t)).status_code == 200


def test_registration_can_be_disabled_after_bootstrap(client, monkeypatch):
    assert register(client).status_code == 201
    monkeypatch.setattr(get_settings(), "registration_enabled", False)
    assert register(client, "late@example.com").status_code == 403


def test_auth_endpoints_are_rate_limited(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "rate_limit_auth_per_minute", 3)
    codes = [client.post("/api/auth/login", json={"email": "a@example.com", "password": "x"}).status_code for _ in range(5)]
    assert codes[:3] == [401, 401, 401] and codes[3:] == [429, 429]
    assert "retry-after" in client.post("/api/auth/login", json={"email": "a@example.com", "password": "x"}).headers


def test_audit_log_records_events_without_secrets(client, db):
    register(client)
    client.post("/api/auth/login", json={"email": "admin@example.com", "password": "Wrong-password-1"})
    client.post("/api/auth/login", json={"email": "admin@example.com", "password": PASSWORD})
    rows = db.scalars(select(AuditLog).order_by(AuditLog.created_at)).all()
    assert {r.action for r in rows} >= {"auth.register", "auth.login_failed", "auth.login"}
    assert PASSWORD not in str([r.details for r in rows])
