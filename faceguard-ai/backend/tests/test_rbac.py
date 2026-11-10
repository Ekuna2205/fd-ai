from tests.conftest import PASSWORD, headers, register


def test_viewer_cannot_manage_users(client, viewer):
    assert client.get("/api/users", headers=viewer["h"]).status_code == 403
    r = client.patch(f"/api/users/{viewer['user']['id']}", json={"role": "administrator"}, headers=viewer["h"])
    assert r.status_code == 403


def test_users_endpoint_requires_authentication(client):
    assert client.get("/api/users").status_code == 401


def test_admin_lists_users(client, admin, viewer):
    r = client.get("/api/users", headers=admin["h"])
    assert r.status_code == 200 and r.json()["total"] == 2
    assert {u["role"] for u in r.json()["items"]} == {"administrator", "viewer"}


def test_admin_can_assign_every_role_and_it_applies_immediately(client, admin, viewer):
    for role in ("researcher", "operator", "viewer", "administrator"):
        r = client.patch(f"/api/users/{viewer['user']['id']}", json={"role": role}, headers=admin["h"])
        assert r.status_code == 200 and r.json()["role"] == role
        # the role comes from the database, not the token issued earlier
        assert client.get("/api/auth/me", headers=viewer["h"]).json()["role"] == role


def test_promoted_user_gains_admin_access(client, admin, viewer):
    client.patch(f"/api/users/{viewer['user']['id']}", json={"role": "administrator"}, headers=admin["h"])
    assert client.get("/api/users", headers=viewer["h"]).status_code == 200


def test_admin_cannot_change_own_role_or_status(client, admin):
    r = client.patch(f"/api/users/{admin['user']['id']}", json={"role": "viewer"}, headers=admin["h"])
    assert r.status_code == 400


def test_invalid_role_and_unknown_user(client, admin, viewer):
    assert client.patch(f"/api/users/{viewer['user']['id']}", json={"role": "root"}, headers=admin["h"]).status_code == 422
    missing = "00000000-0000-4000-8000-000000000000"
    assert client.patch(f"/api/users/{missing}", json={"role": "viewer"}, headers=admin["h"]).status_code == 404
    assert client.patch("/api/users/not-a-uuid", json={"role": "viewer"}, headers=admin["h"]).status_code == 422


def test_deactivated_user_loses_access_with_existing_token(client, admin, viewer):
    assert client.get("/api/auth/me", headers=viewer["h"]).status_code == 200
    client.patch(f"/api/users/{viewer['user']['id']}", json={"is_active": False}, headers=admin["h"])
    assert client.get("/api/auth/me", headers=viewer["h"]).status_code == 401


def test_role_change_is_audited(client, admin, viewer, db):
    from sqlalchemy import select
    from app.models.system import AuditLog
    client.patch(f"/api/users/{viewer['user']['id']}", json={"role": "operator"}, headers=admin["h"])
    row = db.scalar(select(AuditLog).where(AuditLog.action == "user.update"))
    assert row.details["role"] == {"from": "viewer", "to": "operator"}
