"""Refresh tokens, logout, password change/reset, profile editing."""
from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import get_settings
from app.models.user import PasswordResetToken, RefreshToken
from app.services import email_service
from tests.conftest import PASSWORD, headers, register

NEW_PASSWORD = "Another-pass-42"


def _login(client, email="admin@example.com", password=PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_login_returns_refresh_token(client, admin):
    body = _login(client).json()
    assert body["refresh_token"] and body["refresh_expires_in"] > body["expires_in"]


def test_refresh_rotates_and_old_token_stops_working(client, admin):
    first = _login(client).json()
    r = client.post("/api/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert r.status_code == 200
    second = r.json()
    assert second["refresh_token"] != first["refresh_token"]
    assert client.get("/api/auth/me", headers=headers(second["access_token"])).status_code == 200
    # replaying the used token fails ...
    assert client.post("/api/auth/refresh", json={"refresh_token": first["refresh_token"]}).status_code == 401
    # ... and revokes the whole family, including the newest token
    assert client.post("/api/auth/refresh", json={"refresh_token": second["refresh_token"]}).status_code == 401


def test_refresh_rejects_garbage_and_expired(client, admin, db):
    assert client.post("/api/auth/refresh", json={"refresh_token": "x" * 40}).status_code == 401
    assert client.post("/api/auth/refresh", json={"refresh_token": "short"}).status_code == 422
    tok = _login(client).json()["refresh_token"]
    for row in db.query(RefreshToken).all():
        row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()
    assert client.post("/api/auth/refresh", json={"refresh_token": tok}).status_code == 401


def test_refresh_fails_for_deactivated_user(client, admin, viewer):
    tok = _login(client, "viewer@example.com").json()["refresh_token"]
    client.patch(f"/api/users/{viewer['user']['id']}", json={"is_active": False}, headers=admin["h"])
    assert client.post("/api/auth/refresh", json={"refresh_token": tok}).status_code == 401


def test_refresh_tokens_are_stored_hashed(client, admin, db):
    tok = _login(client).json()["refresh_token"]
    assert all(tok != row.token_hash and len(row.token_hash) == 64 for row in db.query(RefreshToken).all())


def test_logout_revokes_access_and_refresh(client, admin):
    body = _login(client).json()
    h = headers(body["access_token"])
    assert client.post("/api/auth/logout", json={"refresh_token": body["refresh_token"]}, headers=h).status_code == 204
    assert client.get("/api/auth/me", headers=h).status_code == 401
    assert client.post("/api/auth/refresh", json={"refresh_token": body["refresh_token"]}).status_code == 401


def test_logout_without_body_still_works(client, admin):
    assert client.post("/api/auth/logout", headers=admin["h"]).status_code == 204


def test_change_password_flow(client, admin):
    other = _login(client).json()  # a second session
    r = client.post("/api/auth/change-password", headers=admin["h"],
                    json={"current_password": PASSWORD, "new_password": NEW_PASSWORD})
    assert r.status_code == 200
    fresh = r.json()
    assert client.get("/api/auth/me", headers=headers(fresh["access_token"])).status_code == 200
    # old access tokens and other sessions' refresh tokens are dead
    assert client.get("/api/auth/me", headers=admin["h"]).status_code == 401
    assert client.get("/api/auth/me", headers=headers(other["access_token"])).status_code == 401
    assert client.post("/api/auth/refresh", json={"refresh_token": other["refresh_token"]}).status_code == 401
    assert _login(client).status_code == 401
    assert _login(client, password=NEW_PASSWORD).status_code == 200


def test_change_password_validation(client, admin):
    url = "/api/auth/change-password"
    wrong = client.post(url, headers=admin["h"], json={"current_password": "nope-nope-1", "new_password": NEW_PASSWORD})
    assert wrong.status_code == 400
    same = client.post(url, headers=admin["h"], json={"current_password": PASSWORD, "new_password": PASSWORD})
    assert same.status_code == 400
    weak = client.post(url, headers=admin["h"], json={"current_password": PASSWORD, "new_password": "short"})
    assert weak.status_code == 422
    assert client.post(url, json={"current_password": PASSWORD, "new_password": NEW_PASSWORD}).status_code == 401


def test_profile_update_changes_only_the_name(client, admin):
    r = client.patch("/api/auth/me", headers=admin["h"], json={"full_name": "  Ada   Lovelace "})
    assert r.status_code == 200 and r.json()["full_name"] == "Ada Lovelace" and r.json()["role"] == "administrator"


def test_profile_update_cannot_escalate(client, viewer):
    for payload in ({"full_name": "Vic V", "role": "administrator"}, {"full_name": "Vic V", "is_active": True},
                    {"full_name": "Vic V", "email": "x@example.com"}):
        assert client.patch("/api/auth/me", headers=viewer["h"], json=payload).status_code == 422
    assert client.get("/api/auth/me", headers=viewer["h"]).json()["role"] == "viewer"


# ---- password reset ----
def test_forgot_password_is_unavailable_without_smtp(client, admin):
    assert get_settings().smtp_configured is False
    assert client.get("/api/auth/password-reset/status").json() == {"email_reset_available": False}
    r = client.post("/api/auth/forgot-password", json={"email": "admin@example.com"})
    assert r.status_code == 503  # honest failure, not a fake success


@pytest.fixture
def smtp(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "smtp_host", "smtp.invalid")
    monkeypatch.setattr(s, "smtp_from", "noreply@example.com")
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(email_service, "send", lambda to, subject, body: sent.append((to, body)))
    return sent


def _token_from(sent):
    body = sent[-1][1]
    return body.split("token=")[1].split()[0]


def test_reset_password_end_to_end(client, admin, smtp):
    r = client.post("/api/auth/forgot-password", json={"email": "ADMIN@example.com"})
    assert r.status_code == 202 and len(smtp) == 1 and smtp[0][0] == "admin@example.com"
    token = _token_from(smtp)
    assert client.post("/api/auth/reset-password", json={"token": token, "new_password": NEW_PASSWORD}).status_code == 200
    assert _login(client, password=NEW_PASSWORD).status_code == 200
    assert _login(client).status_code == 401
    assert client.get("/api/auth/me", headers=admin["h"]).status_code == 401  # old sessions end
    # the token works once
    assert client.post("/api/auth/reset-password", json={"token": token, "new_password": "Third-pass-77x"}).status_code == 400


def test_forgot_password_does_not_reveal_unknown_accounts(client, admin, smtp):
    r = client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"})
    assert r.status_code == 202 and smtp == []
    assert r.json()["detail"] == client.post("/api/auth/forgot-password", json={"email": "admin@example.com"}).json()["detail"]


def test_reset_token_expiry_and_garbage(client, admin, smtp, db):
    client.post("/api/auth/forgot-password", json={"email": "admin@example.com"})
    token = _token_from(smtp)
    assert all(token != t.token_hash for t in db.query(PasswordResetToken).all())  # stored hashed
    for t in db.query(PasswordResetToken).all():
        t.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()
    assert client.post("/api/auth/reset-password", json={"token": token, "new_password": NEW_PASSWORD}).status_code == 400
    assert client.post("/api/auth/reset-password", json={"token": "z" * 43, "new_password": NEW_PASSWORD}).status_code == 400


def test_new_reset_request_invalidates_the_previous_token(client, admin, smtp):
    client.post("/api/auth/forgot-password", json={"email": "admin@example.com"})
    first = _token_from(smtp)
    client.post("/api/auth/forgot-password", json={"email": "admin@example.com"})
    assert client.post("/api/auth/reset-password", json={"token": first, "new_password": NEW_PASSWORD}).status_code == 400
    assert client.post("/api/auth/reset-password", json={"token": _token_from(smtp), "new_password": NEW_PASSWORD}).status_code == 200


def test_inactive_user_gets_no_reset_mail(client, admin, viewer, smtp):
    client.patch(f"/api/users/{viewer['user']['id']}", json={"is_active": False}, headers=admin["h"])
    assert client.post("/api/auth/forgot-password", json={"email": "viewer@example.com"}).status_code == 202
    assert smtp == []
