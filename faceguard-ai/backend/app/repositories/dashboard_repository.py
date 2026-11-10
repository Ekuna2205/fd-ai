import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.ai import AIModel, ModelEvaluation
from app.models.enums import VerificationStatus as S
from app.models.verification import VerificationResult as R, VerificationSession as VS

FAILED = (S.NO_FACE, S.MULTIPLE_FACES, S.ERROR)


def owned_by(stmt: Select, user_id: uuid.UUID | None) -> Select:
    """Restricts a query over verification results to one user's sessions.

    `user_id=None` means "no restriction" and is ONLY for the explicit administrator aggregate scope;
    ordinary callers must always pass the authenticated user's id. Ownership lives on
    verification_sessions.user_id, so results of sessions with no owner are never visible to normal users.
    """
    if user_id is None:
        return stmt
    return stmt.join(VS, VS.id == R.session_id).where(VS.user_id == user_id)


def status_counts(db: Session, user_id: uuid.UUID | None) -> dict[S, int]:
    rows = db.execute(owned_by(select(R.status, func.count()).select_from(R), user_id).group_by(R.status)).all()
    return {status: n for status, n in rows}


def daily_counts(db: Session, start: datetime, user_id: uuid.UUID | None) -> dict[date, dict[S, int]]:
    day = func.date(R.created_at)
    rows = db.execute(
        owned_by(select(day, R.status, func.count()).select_from(R), user_id)
        .where(R.created_at >= start, R.status.in_((S.REAL, S.FAKE, S.UNCERTAIN)))
        .group_by(day, R.status)
    ).all()
    out: dict[date, dict[S, int]] = {}
    for d, status, n in rows:
        d = d if isinstance(d, date) else date.fromisoformat(str(d))  # SQLite returns text
        out.setdefault(d, {})[status] = n
    return out


def spoof_category_counts(db: Session, user_id: uuid.UUID | None) -> list[tuple[str, int]]:
    rows = db.execute(
        owned_by(select(R.spoof_type, func.count()).select_from(R), user_id)
        .where(R.status == S.FAKE, R.spoof_type.is_not(None))
        .group_by(R.spoof_type)
        .order_by(func.count().desc(), R.spoof_type)
    ).all()
    return [(t.value, n) for t, n in rows]


def recent_results(db: Session, limit: int, user_id: uuid.UUID | None) -> list[R]:
    stmt = owned_by(select(R), user_id).where(R.status != S.PROCESSING).order_by(R.created_at.desc()).limit(limit)
    return list(db.scalars(stmt))


def get_owned_result(db: Session, result_id: uuid.UUID, user_id: uuid.UUID) -> R | None:
    """One result, only if it belongs to `user_id`. Returns None for both "missing" and "someone else's"."""
    return db.scalar(owned_by(select(R), user_id).where(R.id == result_id))


def active_model_with_latest_evaluation(db: Session) -> tuple[AIModel, ModelEvaluation | None] | None:
    model = db.scalar(select(AIModel).where(AIModel.is_active.is_(True)))
    if model is None:
        return None
    evaluation = db.scalar(
        select(ModelEvaluation)
        .where(ModelEvaluation.model_id == model.id)
        .order_by(ModelEvaluation.evaluated_at.desc())
        .limit(1)
    )
    return model, evaluation


def window_start(days: int) -> datetime:
    today = datetime.now(UTC).date()
    return datetime.combine(today - timedelta(days=days - 1), datetime.min.time(), tzinfo=UTC)
