from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.core.config import get_settings
from app.models.system import AuditLog
from app.models.user import User
from app.models.verification import VerificationResult, VerificationSession
from app.services import retention_service as rs
from tests.conftest import add_result


def count(db, model):
    db.expire_all()
    return db.scalar(select(func.count()).select_from(model))


def test_disabled_by_default_and_with_zero_days(db):
    add_result(db, "REAL", created=datetime.now(UTC) - timedelta(days=500))
    assert get_settings().retention_days == 0
    assert rs.purge(db) == {"verifications": 0, "audit_logs": 0} and rs.purge(db, 0)["verifications"] == 0
    assert count(db, VerificationResult) == 1


def test_expires_only_old_results_and_cascades(db):
    now = datetime.now(UTC)
    old = add_result(db, "REAL", created=now - timedelta(days=40))
    add_result(db, "FAKE", "PHONE_SCREEN", created=now - timedelta(days=5))
    db.get(VerificationSession, old.session_id).created_at = now - timedelta(days=40)
    db.commit()
    assert rs.purge(db, 30)["verifications"] == 1
    assert count(db, VerificationSession) == 1 and count(db, VerificationResult) == 1
    assert db.scalar(select(VerificationResult.status)).value == "FAKE"


def test_never_deletes_users_and_records_the_purge(db, admin):
    s = add_result(db, "REAL", user_id=admin["user"]["id"])
    db.get(VerificationSession, s.session_id).created_at = datetime.now(UTC) - timedelta(days=400)
    db.commit()
    rs.purge(db, 30)
    assert count(db, User) == 1
    row = db.scalar(select(AuditLog).where(AuditLog.action == "retention.purge"))
    assert row.details["verifications"] == 1


def test_security_events_are_kept_at_least_90_days(db):
    db.add_all([AuditLog(action="old", created_at=datetime.now(UTC) - timedelta(days=100)),
                AuditLog(action="recent", created_at=datetime.now(UTC) - timedelta(days=60))])
    db.commit()
    rs.purge(db, 30)  # results expire at 30 days, but the 60-day-old audit entry survives
    actions = {a.action for a in db.scalars(select(AuditLog))}
    assert "recent" in actions and "old" not in actions


def test_runs_at_startup_when_enabled(monkeypatch, db):
    from fastapi.testclient import TestClient
    from app.main import create_app
    s = add_result(db, "REAL")
    db.get(VerificationSession, s.session_id).created_at = datetime.now(UTC) - timedelta(days=100)
    db.commit()
    monkeypatch.setattr(get_settings(), "retention_days", 30)
    with TestClient(create_app()):
        pass
    assert count(db, VerificationSession) == 0
