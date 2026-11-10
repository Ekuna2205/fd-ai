import uuid
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import String, Select, cast, func, or_, select
from sqlalchemy.orm import Session

from app.models.enums import SessionMode, VerificationStatus
from app.models.verification import VerificationResult as R, VerificationSession as VS

SORTABLE = {"created_at": R.created_at, "status": R.status, "processing_ms": R.processing_ms, "confidence": R.confidence}


def _like_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def filtered(user_id: uuid.UUID, *, q: str | None, status: VerificationStatus | None, mode: SessionMode | None,
             date_from: date | None, date_to: date | None) -> Select:
    """Every history query is restricted to the caller's own sessions. There is no bypass parameter."""
    stmt = select(R).join(VS, VS.id == R.session_id).where(VS.user_id == user_id)
    if status:
        stmt = stmt.where(R.status == status)
    if mode:
        stmt = stmt.where(VS.mode == mode)
    if date_from:
        stmt = stmt.where(R.created_at >= datetime.combine(date_from, time.min, tzinfo=UTC))
    if date_to:
        stmt = stmt.where(R.created_at < datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=UTC))
    if q:
        needle = q.strip().lower()
        hex_id = needle.replace("-", "")
        id_text = func.replace(cast(R.id, String), "-", "")  # same on PostgreSQL (dashed) and SQLite (plain hex)
        stmt = stmt.where(or_(func.lower(id_text).like(f"{_like_escape(hex_id)}%", escape="\\"),
                              func.lower(R.explanation).like(f"%{_like_escape(needle)}%", escape="\\")))
    return stmt


def page(db: Session, stmt: Select, sort: str, order: str, page_no: int, size: int) -> tuple[list[R], int]:
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    col = SORTABLE[sort]
    ordered = stmt.order_by(col.desc() if order == "desc" else col.asc(), R.id)  # id = stable tiebreak for paging
    return list(db.scalars(ordered.limit(size).offset((page_no - 1) * size))), total
