from sqlalchemy import select

from app.models.system import AuditLog
from tests.conftest import PASSWORD, add_result, register


def test_audit_log_is_administrator_only(client, admin, viewer, operator):
    assert client.get("/api/admin/audit-logs").status_code == 401
    assert client.get("/api/admin/audit-logs", headers=viewer["h"]).status_code == 403
    assert client.get("/api/admin/audit-logs", headers=operator["h"]).status_code == 403
    assert client.get("/api/admin/audit-logs", headers=admin["h"]).status_code == 200


def test_lists_events_newest_first_with_actor_and_filter(client, admin, viewer):
    client.post("/api/auth/login", json={"email": "viewer@example.com", "password": "wrong-password-1"})
    body = client.get("/api/admin/audit-logs", params={"page_size": 100}, headers=admin["h"]).json()
    actions = [i["action"] for i in body["items"]]
    assert "auth.register" in actions and "auth.login_failed" in actions and body["total"] == len(actions)
    stamps = [i["created_at"] for i in body["items"]]
    assert stamps == sorted(stamps, reverse=True)
    only = client.get("/api/admin/audit-logs", params={"action": "auth.register"}, headers=admin["h"]).json()
    assert only["total"] == 2 and {i["user_email"] for i in only["items"]} == {"admin@example.com", "viewer@example.com"}


def test_pagination(client, admin, viewer):
    p1 = client.get("/api/admin/audit-logs", params={"page_size": 1, "page": 1}, headers=admin["h"]).json()
    p2 = client.get("/api/admin/audit-logs", params={"page_size": 1, "page": 2}, headers=admin["h"]).json()
    assert len(p1["items"]) == len(p2["items"]) == 1 and p1["items"][0]["id"] != p2["items"][0]["id"]
    assert client.get("/api/admin/audit-logs", params={"page_size": 1000}, headers=admin["h"]).status_code == 422


def test_audit_entries_never_contain_credentials_or_tokens(client, admin, viewer, db):
    client.post("/api/auth/login", json={"email": "admin@example.com", "password": PASSWORD})
    blob = str([(a.action, a.details) for a in db.scalars(select(AuditLog))])
    assert PASSWORD not in blob and "eyJ" not in blob  # no password, no JWT
