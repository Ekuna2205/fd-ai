"""Regression tests for broken access control (verification detail + dashboard).

Ownership lives on verification_sessions.user_id. These tests insert rows directly so they do not depend on the
face-detection model files and also run offline.
"""
import pytest
from sqlalchemy import select

from app.models.system import AuditLog
from tests.conftest import add_result, headers, register

MISSING = "00000000-0000-4000-8000-000000000000"


def _user(client, email, name):
    body = register(client, email, name).json()
    return {"user": body["user"], "h": headers(body["access_token"])}


@pytest.fixture
def user_a(client, admin):
    return _user(client, "alice@example.com", "Alice A")


@pytest.fixture
def user_b(client, admin):
    return _user(client, "bob@example.com", "Bob B")


# ---------- verification detail ----------
def test_user_a_can_read_their_own_verification(client, user_a, db):
    r = add_result(db, "UNCERTAIN", user_id=user_a["user"]["id"])
    resp = client.get(f"/api/verifications/{r.id}", headers=user_a["h"])
    assert resp.status_code == 200 and resp.json()["id"] == str(r.id)


def test_user_b_cannot_read_user_a_verification(client, user_a, user_b, db):
    r = add_result(db, "UNCERTAIN", user_id=user_a["user"]["id"])
    resp = client.get(f"/api/verifications/{r.id}", headers=user_b["h"])
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Verification not found."}  # nothing about the real record leaks


def test_other_users_record_looks_identical_to_a_missing_one(client, user_a, user_b, db):
    r = add_result(db, "UNCERTAIN", user_id=user_a["user"]["id"])
    theirs = client.get(f"/api/verifications/{r.id}", headers=user_b["h"])
    missing = client.get(f"/api/verifications/{MISSING}", headers=user_b["h"])
    assert (theirs.status_code, theirs.json()) == (missing.status_code, missing.json())  # no ID probing


def test_administrator_has_no_per_user_verification_access(client, admin, user_a, db):
    r = add_result(db, "UNCERTAIN", user_id=user_a["user"]["id"])
    assert client.get(f"/api/verifications/{r.id}", headers=admin["h"]).status_code == 404


def test_orphaned_results_are_not_readable_by_anyone(client, admin, user_a, db):
    r = add_result(db, "UNCERTAIN", user_id=None)
    for who in (admin, user_a):
        assert client.get(f"/api/verifications/{r.id}", headers=who["h"]).status_code == 404


def test_denied_access_is_audited_without_leaking_content(client, user_a, user_b, db):
    r = add_result(db, "UNCERTAIN", user_id=user_a["user"]["id"])
    client.get(f"/api/verifications/{r.id}", headers=user_b["h"])
    row = db.scalar(select(AuditLog).where(AuditLog.action == "verification.access_denied"))
    assert row is not None and str(row.user_id) == user_b["user"]["id"] and row.entity_id == str(r.id)
    assert not row.details  # no biometric or result content


# ---------- dashboard ----------
def test_dashboard_is_scoped_to_the_authenticated_user(client, user_a, user_b, db):
    for status in ("REAL", "REAL", "FAKE", "UNCERTAIN"):
        add_result(db, status, "PHONE_SCREEN" if status == "FAKE" else None, user_id=user_a["user"]["id"])
    add_result(db, "NO_FACE", user_id=user_b["user"]["id"])
    add_result(db, "REAL", user_id=None)  # orphan: belongs to nobody

    a = client.get("/api/dashboard/overview", headers=user_a["h"]).json()
    b = client.get("/api/dashboard/overview", headers=user_b["h"]).json()

    assert (a["totals"]["attempts"], a["totals"]["real"], a["totals"]["fake"], a["totals"]["failed"]) == (4, 2, 1, 0)
    assert len(a["recent"]) == 4 and a["spoof_categories"] == [{"category": "PHONE_SCREEN", "count": 1}]
    assert (b["totals"]["attempts"], b["totals"]["real"], b["totals"]["failed"]) == (1, 0, 1)
    assert [x["status"] for x in b["recent"]] == ["NO_FACE"]
    assert not ({x["id"] for x in a["recent"]} & {x["id"] for x in b["recent"]})


def test_new_user_dashboard_is_empty_even_when_others_have_data(client, user_a, user_b, db):
    add_result(db, "REAL", user_id=user_a["user"]["id"])
    body = client.get("/api/dashboard/overview", headers=user_b["h"]).json()
    assert body["totals"]["attempts"] == 0 and body["recent"] == [] and body["daily"] == []


def test_scope_all_is_administrator_only(client, admin, user_a, user_b, db):
    add_result(db, "REAL", user_id=user_a["user"]["id"])
    add_result(db, "FAKE", "PRINTED_PHOTO", user_id=user_b["user"]["id"])
    assert client.get("/api/dashboard/overview?scope=all", headers=user_a["h"]).status_code == 403
    allv = client.get("/api/dashboard/overview?scope=all", headers=admin["h"]).json()
    assert allv["totals"]["attempts"] == 2
    own = client.get("/api/dashboard/overview", headers=admin["h"]).json()  # default stays "own"
    assert own["totals"]["attempts"] == 0


def test_invalid_scope_is_rejected(client, admin):
    assert client.get("/api/dashboard/overview?scope=everyone", headers=admin["h"]).status_code == 422


# ---------- authentication required everywhere ----------
@pytest.mark.parametrize("method,path", [
    ("GET", "/api/auth/me"), ("PATCH", "/api/auth/me"), ("POST", "/api/auth/logout"),
    ("POST", "/api/auth/change-password"),
    ("GET", "/api/users"), ("PATCH", f"/api/users/{MISSING}"),
    ("GET", "/api/dashboard/overview"), ("GET", "/api/dashboard/overview?scope=all"),
    ("GET", f"/api/verifications/{MISSING}"),
    ("GET", "/api/face/capabilities"), ("POST", "/api/face/detect"), ("POST", "/api/face/verify"),
    ("POST", "/api/uploads/image"), ("POST", "/api/uploads/video"),
])
def test_protected_endpoints_reject_unauthenticated_requests(client, method, path):
    assert client.request(method, path).status_code == 401


def test_garbage_and_malformed_tokens_are_rejected(client):
    for bad in ("garbage", "a.b.c"):
        r = client.get(f"/api/verifications/{MISSING}", headers={"Authorization": f"Bearer {bad}"})
        assert r.status_code == 401
