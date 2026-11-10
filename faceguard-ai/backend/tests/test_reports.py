import csv
import io
from datetime import UTC, datetime, timedelta

from tests.conftest import add_result


def _summary(client, h, **params):
    return client.get("/api/reports/summary", params=params, headers=h)


def test_requires_authentication(client):
    assert client.get("/api/reports/summary").status_code == 401
    assert client.get("/api/reports/export").status_code == 401


def test_empty_window_has_no_series_and_null_rate(client, admin):
    body = _summary(client, admin["h"]).json()
    assert body["series"] == [] and body["totals"]["attempts"] == 0 and body["totals"]["success_rate"] is None
    assert body["avg_processing_ms"] is None and body["scope"] == "own"


def test_totals_distribution_and_categories_for_my_data_only(client, admin, viewer, db):
    u, other = admin["user"]["id"], viewer["user"]["id"]
    for status, spoof in [("REAL", None), ("REAL", None), ("FAKE", "PRINTED_PHOTO"), ("UNCERTAIN", None), ("NO_FACE", None)]:
        add_result(db, status, spoof, user_id=u)
    add_result(db, "FAKE", "PHONE_SCREEN", user_id=other)  # must not leak
    add_result(db, "PROCESSING", user_id=u)
    body = _summary(client, admin["h"]).json()
    t = body["totals"]
    assert (t["attempts"], t["real"], t["fake"], t["uncertain"], t["failed"]) == (5, 2, 1, 1, 1)
    assert t["success_rate"] == 0.4
    assert body["spoof_categories"] == [{"category": "PRINTED_PHOTO", "count": 1}]
    assert {d["status"]: d["count"] for d in body["status_distribution"]} == {"REAL": 2, "FAKE": 1, "UNCERTAIN": 1, "NO_FACE": 1}


def test_periods_bucket_and_zero_fill(client, admin, db):
    u, now = admin["user"]["id"], datetime.now(UTC)
    add_result(db, "REAL", user_id=u, created=now)
    add_result(db, "FAKE", "PHONE_SCREEN", user_id=u, created=now - timedelta(days=20))
    day = _summary(client, admin["h"], period="day", days=30).json()["series"]
    assert len(day) == 30 and day[-1]["real"] == 1 and sum(p["fake"] for p in day) == 1
    week = _summary(client, admin["h"], period="week", days=30).json()["series"]
    assert 4 <= len(week) <= 6 and all(datetime.fromisoformat(p["bucket"]).weekday() == 0 for p in week)
    assert sum(p["real"] + p["fake"] for p in week) == 2
    month = _summary(client, admin["h"], period="month", days=90).json()["series"]
    assert all(p["bucket"].endswith("-01") for p in month) and sum(p["real"] + p["fake"] for p in month) == 2


def test_window_excludes_old_records(client, admin, db):
    add_result(db, "REAL", user_id=admin["user"]["id"], created=datetime.now(UTC) - timedelta(days=100))
    assert _summary(client, admin["h"], days=30).json()["totals"]["attempts"] == 0
    assert _summary(client, admin["h"], days=365).json()["totals"]["attempts"] == 1


def test_all_scope_is_administrator_only_and_counts_everyone(client, admin, viewer, db):
    add_result(db, "REAL", user_id=admin["user"]["id"])
    add_result(db, "FAKE", "PHONE_SCREEN", user_id=viewer["user"]["id"])
    assert _summary(client, viewer["h"], scope="all").status_code == 403
    assert client.get("/api/reports/export", params={"scope": "all"}, headers=viewer["h"]).status_code == 403
    body = _summary(client, admin["h"], scope="all").json()
    assert body["scope"] == "all" and body["totals"]["attempts"] == 2


def test_invalid_parameters(client, admin):
    for p in ({"period": "year"}, {"days": 0}, {"days": 4000}, {"scope": "everyone"}):
        assert _summary(client, admin["h"], **p).status_code == 422, p


def test_csv_report_export(client, admin, db):
    add_result(db, "REAL", user_id=admin["user"]["id"])
    r = client.get("/api/reports/export", params={"days": 7}, headers=admin["h"])
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(r.text)))
    assert rows[0][0].startswith("FaceGuard AI report") and ["period_start", "real", "fake", "uncertain", "failed"] in rows
    assert ["total_attempts", "1"] in rows and ["real", "1"] in rows
