import csv
import io
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.models.system import AuditLog
from app.models.verification import VerificationResult, VerificationSession
from tests.conftest import add_result, headers


def _ids(r):
    return [i["id"] for i in r.json()["items"]]


def test_history_requires_authentication(client):
    for path in ("/api/verifications", "/api/verifications/export"):
        assert client.get(path).status_code == 401


def test_history_lists_only_my_records_even_for_administrators(client, admin, viewer, db):
    mine = add_result(db, "REAL", user_id=admin["user"]["id"])
    theirs = add_result(db, "FAKE", "PHONE_SCREEN", user_id=viewer["user"]["id"])
    orphan = add_result(db, "REAL")
    a = client.get("/api/verifications", headers=admin["h"]).json()
    assert [i["id"] for i in a["items"]] == [str(mine.id)] and a["total"] == 1
    b = client.get("/api/verifications", headers=viewer["h"]).json()
    assert [i["id"] for i in b["items"]] == [str(theirs.id)]
    assert str(orphan.id) not in str(a) + str(b)


def test_search_cannot_reach_other_users_records(client, admin, viewer, db):
    theirs = add_result(db, "REAL", user_id=viewer["user"]["id"])
    r = client.get("/api/verifications", params={"q": str(theirs.id)}, headers=admin["h"])
    assert r.json()["total"] == 0


def test_filters_by_status_mode_and_dates(client, admin, db):
    u = admin["user"]["id"]
    now = datetime.now(UTC)
    add_result(db, "REAL", user_id=u, created=now)
    add_result(db, "FAKE", "PRINTED_PHOTO", user_id=u, created=now - timedelta(days=10))
    add_result(db, "UNCERTAIN", user_id=u, created=now - timedelta(days=40))
    get = lambda **p: client.get("/api/verifications", params=p, headers=admin["h"]).json()["total"]  # noqa: E731
    assert get() == 3 and get(status="FAKE") == 1 and get(mode="LIVE") == 3 and get(mode="UPLOAD_VIDEO") == 0
    assert get(date_from=(now - timedelta(days=15)).date().isoformat()) == 2
    assert get(date_to=(now - timedelta(days=30)).date().isoformat()) == 1
    assert get(date_from=(now - timedelta(days=15)).date().isoformat(), date_to=(now - timedelta(days=5)).date().isoformat()) == 1


def test_search_by_id_prefix_dashed_or_plain_and_by_explanation(client, admin, db):
    u = admin["user"]["id"]
    r1 = add_result(db, "UNCERTAIN", user_id=u)
    r2 = add_result(db, "REAL", user_id=u)
    r1.explanation = "Face too dark to assess"
    db.commit()
    search = lambda q: _ids(client.get("/api/verifications", params={"q": q}, headers=admin["h"]))  # noqa: E731
    assert search(str(r2.id)[:8]) == [str(r2.id)]
    assert search(str(r2.id).replace("-", "")[:12].upper()) == [str(r2.id)]
    assert search("too DARK") == [str(r1.id)]
    assert search("nothing-matches") == []


def test_wildcards_in_search_are_literal(client, admin, db):
    u = admin["user"]["id"]
    r = add_result(db, "UNCERTAIN", user_id=u)
    r.explanation = "plain text"
    db.commit()
    for q in ("%", "_", "p%t", "\\"):
        assert client.get("/api/verifications", params={"q": q}, headers=admin["h"]).json()["total"] == 0


def test_sql_injection_strings_are_inert(client, admin, db):
    add_result(db, "REAL", user_id=admin["user"]["id"])
    for q in ("'; DROP TABLE verification_results; --", "' OR '1'='1", "%' OR 1=1 --"):
        r = client.get("/api/verifications", params={"q": q}, headers=admin["h"])
        assert r.status_code == 200 and r.json()["total"] == 0
    assert db.scalar(select(func.count()).select_from(VerificationResult)) == 1


def test_sorting_and_pagination_are_stable(client, admin, db):
    u = admin["user"]["id"]
    now = datetime.now(UTC)
    for i in range(7):
        add_result(db, "REAL", user_id=u, confidence=i / 10, created=now - timedelta(minutes=i))
    get = lambda **p: client.get("/api/verifications", params=p, headers=admin["h"]).json()  # noqa: E731
    p1, p2, p3 = (get(page=n, page_size=3) for n in (1, 2, 3))
    assert [len(p["items"]) for p in (p1, p2, p3)] == [3, 3, 1] and p1["total"] == 7
    seen = [i["id"] for p in (p1, p2, p3) for i in p["items"]]
    assert len(set(seen)) == 7  # no duplicates or gaps across pages
    asc = get(sort="confidence", order="asc", page_size=10)["items"]
    assert [i["confidence"] for i in asc] == sorted(i["confidence"] for i in asc)
    assert get(page=99)["items"] == []


def test_invalid_parameters_are_rejected(client, admin):
    for params in ({"page": 0}, {"page_size": 500}, {"sort": "password"}, {"order": "sideways"}, {"status": "MAYBE"},
                   {"date_from": "yesterday"}, {"q": "x" * 200}):
        assert client.get("/api/verifications", params=params, headers=admin["h"]).status_code == 422, params


def test_csv_export_is_scoped_filtered_and_audited(client, admin, viewer, db):
    add_result(db, "REAL", user_id=admin["user"]["id"])
    add_result(db, "FAKE", "REPLAY_VIDEO", user_id=admin["user"]["id"])
    add_result(db, "REAL", user_id=viewer["user"]["id"])
    r = client.get("/api/verifications/export", params={"status": "FAKE"}, headers=admin["h"])
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"] and r.headers["cache-control"] == "private, no-store"
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert len(rows) == 1 and rows[0]["status"] == "FAKE" and rows[0]["spoof_type"] == "REPLAY_VIDEO"
    assert len(list(csv.DictReader(io.StringIO(client.get("/api/verifications/export", headers=viewer["h"]).text)))) == 1
    assert db.scalar(select(AuditLog).where(AuditLog.action == "verification.export")) is not None


def test_csv_export_neutralises_formula_injection(client, admin, db):
    r = add_result(db, "UNCERTAIN", user_id=admin["user"]["id"])
    r.explanation = '=HYPERLINK("http://evil.example","click")'
    db.commit()
    body = client.get("/api/verifications/export", headers=admin["h"]).text
    row = list(csv.DictReader(io.StringIO(body)))[0]
    assert row["explanation"].startswith("'=")


def test_owner_can_delete_and_it_cascades(client, admin, db):
    rid = add_result(db, "REAL", user_id=admin["user"]["id"]).id
    assert client.delete(f"/api/verifications/{rid}", headers=admin["h"]).status_code == 204
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(VerificationResult)) == 0
    assert db.scalar(select(func.count()).select_from(VerificationSession)) == 0
    assert client.get(f"/api/verifications/{rid}", headers=admin["h"]).status_code == 404
    assert db.scalar(select(AuditLog).where(AuditLog.action == "verification.delete")) is not None


def test_cannot_delete_other_users_or_orphan_records_even_as_admin(client, admin, viewer, db):
    theirs = add_result(db, "REAL", user_id=viewer["user"]["id"])
    orphan = add_result(db, "REAL")
    assert client.delete(f"/api/verifications/{theirs.id}", headers=admin["h"]).status_code == 404
    assert client.delete(f"/api/verifications/{orphan.id}", headers=admin["h"]).status_code == 404
    assert client.delete(f"/api/verifications/{theirs.id}", headers=headers("bad")).status_code == 401
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(VerificationResult)) == 2
