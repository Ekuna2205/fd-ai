import csv
import io
import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.errors import NotFound
from app.models.user import User
from app.models.verification import VerificationResult, VerificationSession
from app.repositories import dashboard_repository as dash_repo, history_repository as repo
from app.schemas.history import HistoryItem, HistoryPage
from app.services import audit_service

EXPORT_ROW_CAP = 10_000
_FORMULA_LEAD = ("=", "+", "-", "@", "\t", "\r")


def csv_safe(value) -> str:
    """Neutralises spreadsheet formula injection: a cell that starts with = + - @ is prefixed with an apostrophe."""
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(_FORMULA_LEAD) else text


def _item(r: VerificationResult) -> HistoryItem:
    return HistoryItem(id=r.id, created_at=r.created_at, mode=r.session.mode, status=r.status,
                       spoof_type=r.spoof_type.value if r.spoof_type else None, confidence=r.confidence,
                       face_count=r.face_count, processing_ms=r.processing_ms)


def list_history(db: Session, user: User, *, sort: str, order: str, page: int, page_size: int, **filters) -> HistoryPage:
    rows, total = repo.page(db, repo.filtered(user.id, **filters), sort, order, page, page_size)
    return HistoryPage(items=[_item(r) for r in rows], total=total, page=page, page_size=page_size)


def export_csv(db: Session, user: User, ip: str | None, *, sort: str, order: str, **filters) -> tuple[str, int]:
    rows, total = repo.page(db, repo.filtered(user.id, **filters), sort, order, 1, EXPORT_ROW_CAP)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["id", "created_at_utc", "source", "status", "spoof_type", "confidence", "faces", "processing_ms",
                "model_version", "explanation"])
    for r in rows:
        w.writerow([r.id, r.created_at.isoformat(), r.session.mode.value, r.status.value, csv_safe(r.spoof_type.value if r.spoof_type else ""),
                    "" if r.confidence is None else r.confidence, "" if r.face_count is None else r.face_count,
                    "" if r.processing_ms is None else r.processing_ms, csv_safe(r.model_version), csv_safe(r.explanation)])
    audit_service.record(db, "verification.export", user_id=user.id, ip=ip, details={"rows": len(rows), "total": total})
    db.commit()
    return out.getvalue(), len(rows)


def delete_one(db: Session, user: User, ip: str | None, verification_id: uuid.UUID) -> None:
    """Owner-only (404 otherwise). Removes the session and, by cascade, its results and challenges."""
    r = dash_repo.get_owned_result(db, verification_id, user.id)
    if r is None:
        raise NotFound("Verification not found.")
    session = db.get(VerificationSession, r.session_id)
    db.delete(session)
    audit_service.record(db, "verification.delete", user_id=user.id, ip=ip, entity_type="verification", entity_id=str(verification_id))
    db.commit()
