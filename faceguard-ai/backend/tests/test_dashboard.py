import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tests.conftest import add_evaluation, add_model, add_result as _add_result

TS = (Path(__file__).resolve().parents[2] / "frontend/src/types/dashboard.ts").read_text()

def add_result(db, status, spoof=None, confidence=None, created=None, *, owner):
    """Every result in these tests is owned by the signed-in viewer (the dashboard is per-user)."""
    return _add_result(db, status, spoof, confidence, created, user_id=owner["user"]["id"])


TOTALS = {"attempts", "real", "fake", "uncertain", "failed", "success_rate"}
DAILY = {"date", "real", "fake", "uncertain"}
RECENT = {"id", "created_at", "status", "spoof_type", "confidence"}
MODEL = {"name", "version", "trained", "apcer", "bpcer", "acer", "evaluated_at"}


def test_requires_authentication(client):
    assert client.get("/api/dashboard/overview").status_code == 401


def test_empty_database_returns_zeros_not_invented_data(client, viewer):
    body = client.get("/api/dashboard/overview", headers=viewer["h"]).json()
    assert body["totals"] == {"attempts": 0, "real": 0, "fake": 0, "uncertain": 0, "failed": 0, "success_rate": None}
    assert body["daily"] == [] and body["spoof_categories"] == [] and body["recent"] == []
    assert body["active_model"] is None


def test_counts_come_from_stored_results(client, viewer, db):
    for status, spoof in [("REAL", None)] * 3 + [("FAKE", "PRINTED_PHOTO")] * 2 + [("FAKE", "PHONE_SCREEN")] + [
            ("UNCERTAIN", None), ("NO_FACE", None), ("MULTIPLE_FACES", None), ("ERROR", None), ("PROCESSING", None)]:
        add_result(db, status, spoof, owner=viewer)
    t = client.get("/api/dashboard/overview", headers=viewer["h"]).json()["totals"]
    assert t["attempts"] == 10  # PROCESSING is not a finished attempt
    assert (t["real"], t["fake"], t["uncertain"], t["failed"]) == (3, 3, 1, 3)
    assert t["success_rate"] == pytest.approx(0.3)


def test_spoof_categories_only_count_fake_results(client, viewer, db):
    for spoof in ["PRINTED_PHOTO", "PRINTED_PHOTO", "REPLAY_VIDEO"]:
        add_result(db, "FAKE", spoof, owner=viewer)
    add_result(db, "FAKE", None, owner=viewer)       # model gave no category
    add_result(db, "REAL", None, owner=viewer)
    cats = client.get("/api/dashboard/overview", headers=viewer["h"]).json()["spoof_categories"]
    assert cats == [{"category": "PRINTED_PHOTO", "count": 2}, {"category": "REPLAY_VIDEO", "count": 1}]


def test_daily_series_is_zero_filled_and_respects_window(client, viewer, db):
    now = datetime.now(UTC)
    add_result(db, "REAL", created=now, owner=viewer)
    add_result(db, "FAKE", "PHONE_SCREEN", created=now - timedelta(days=2), owner=viewer)
    add_result(db, "REAL", created=now - timedelta(days=40), owner=viewer)  # outside the 14-day window
    daily = client.get("/api/dashboard/overview", headers=viewer["h"]).json()["daily"]
    assert len(daily) == 14 and daily[-1]["date"] == now.date().isoformat()
    assert sum(d["real"] for d in daily) == 1 and sum(d["fake"] for d in daily) == 1
    assert daily[-3]["fake"] == 1


def test_recent_is_newest_first_limited_and_excludes_processing(client, viewer, db):
    now = datetime.now(UTC)
    for i in range(12):
        add_result(db, "REAL", confidence=0.5, created=now - timedelta(minutes=i), owner=viewer)
    add_result(db, "PROCESSING", created=now + timedelta(minutes=5), owner=viewer)
    recent = client.get("/api/dashboard/overview", headers=viewer["h"]).json()["recent"]
    assert len(recent) == 10 and all(r["status"] != "PROCESSING" for r in recent)
    stamps = [r["created_at"] for r in recent]
    assert stamps == sorted(stamps, reverse=True)


def test_active_model_reports_untrained_flag_and_latest_metrics(client, viewer, db):
    m = add_model(db, trained=False)
    body = client.get("/api/dashboard/overview", headers=viewer["h"]).json()["active_model"]
    assert body["trained"] is False and body["acer"] is None and body["evaluated_at"] is None
    add_evaluation(db, m, apcer=0.04, bpcer=0.02, acer=0.03)
    body = client.get("/api/dashboard/overview", headers=viewer["h"]).json()["active_model"]
    assert (body["apcer"], body["bpcer"], body["acer"]) == (0.04, 0.02, 0.03) and body["evaluated_at"]


def test_inactive_models_are_not_reported(client, viewer, db):
    add_model(db, active=False)
    assert client.get("/api/dashboard/overview", headers=viewer["h"]).json()["active_model"] is None


def test_response_keys_match_frontend_typescript_contract(client, viewer, db):
    add_model(db)
    add_result(db, "FAKE", "PRINTED_PHOTO", confidence=0.9, owner=viewer)
    add_result(db, "REAL", owner=viewer)
    body = client.get("/api/dashboard/overview", headers=viewer["h"]).json()
    assert set(body) == {"totals", "daily", "spoof_categories", "recent", "active_model"}
    assert set(body["totals"]) == TOTALS and set(body["daily"][0]) == DAILY
    assert set(body["recent"][0]) == RECENT and set(body["active_model"]) == MODEL
    assert set(body["spoof_categories"][0]) == {"category", "count"}
    # every key must also be declared in the TypeScript interface the dashboard compiles against
    for key in TOTALS | DAILY | RECENT | MODEL | {"spoof_categories", "active_model", "category", "count"}:
        assert re.search(rf"\b{key}\b", TS), f"{key} missing from types/dashboard.ts"
    for status in ["REAL", "FAKE", "UNCERTAIN", "NO_FACE", "MULTIPLE_FACES", "PROCESSING", "ERROR"]:
        assert f"'{status}'" in TS
