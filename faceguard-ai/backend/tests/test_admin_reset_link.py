"""Administrator-created password-reset links (no SMTP needed)."""
from sqlalchemy import select

from app.models.system import AuditLog
from tests.conftest import PASSWORD, register


def test_admin_creates_a_one_time_link_the_user_can_use(client, admin, viewer, db):
    r = client.post(f"/api/users/{viewer['user']['id']}/reset-link", headers=admin["h"], json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["path"].startswith("/reset-password?token=") and body["signed_out"] is False
    token = body["path"].split("token=", 1)[1]
    ok = client.post("/api/auth/reset-password", json={"token": token, "new_password": "Brand-new-pass-7"})
    assert ok.status_code in (200, 204), ok.text
    assert client.post("/api/auth/login", json={"email": "viewer@example.com", "password": "Brand-new-pass-7"}).status_code == 200
    assert client.post("/api/auth/reset-password", json={"token": token, "new_password": "Another-pass-8"}).status_code == 400
    audit = db.scalar(select(AuditLog).where(AuditLog.action == "user.reset_link_created"))
    assert audit is not None and token not in str(audit.details)


def test_new_link_invalidates_the_previous_one(client, admin, viewer):
    first = client.post(f"/api/users/{viewer['user']['id']}/reset-link", headers=admin["h"], json={}).json()
    client.post(f"/api/users/{viewer['user']['id']}/reset-link", headers=admin["h"], json={})
    token = first["path"].split("token=", 1)[1]
    assert client.post("/api/auth/reset-password", json={"token": token, "new_password": "Brand-new-pass-7"}).status_code == 400


def test_sign_out_revokes_the_users_refresh_tokens(client, admin):
    body = register(client, "v2@example.com", "V Two").json()
    r = client.post(f"/api/users/{body['user']['id']}/reset-link", headers=admin["h"], json={"sign_out": True})
    assert r.json()["signed_out"] is True
    assert client.post("/api/auth/refresh", json={"refresh_token": body["refresh_token"]}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "v2@example.com", "password": PASSWORD}).status_code == 200


def test_only_admins_for_other_active_users(client, admin, viewer):
    assert client.post(f"/api/users/{admin['user']['id']}/reset-link", headers=viewer["h"], json={}).status_code == 403
    assert client.post(f"/api/users/{admin['user']['id']}/reset-link", headers=admin["h"], json={}).status_code == 400
    client.patch(f"/api/users/{viewer['user']['id']}", json={"is_active": False}, headers=admin["h"])
    r = client.post(f"/api/users/{viewer['user']['id']}/reset-link", headers=admin["h"], json={})
    assert r.status_code == 400 and "disabled" in r.json()["detail"]
    assert client.post("/api/users/00000000-0000-0000-0000-000000000000/reset-link", headers=admin["h"], json={}).status_code == 404
