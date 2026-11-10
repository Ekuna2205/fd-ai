"""Optional data-retention purge. Raw images/videos are never stored; this expires the *result records*."""
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.system import AuditLog
from app.models.verification import VerificationSession
from app.services import audit_service

log = logging.getLogger("faceguard.retention")
AUDIT_KEEP_DAYS_FLOOR = 90  # security events are kept at least this long even when results expire sooner


def purge(db: Session, days: int | None = None) -> dict[str, int]:
    """Deletes verification sessions (and, by cascade, their results and challenges) older than `days`.
    `days` defaults to RETENTION_DAYS; 0 or less does nothing. Returns counts. Never touches users or datasets."""
    days = get_settings().retention_days if days is None else days
    if days <= 0:
        return {"verifications": 0, "audit_logs": 0}
    now = datetime.now(UTC)
    old = db.scalars(select(VerificationSession).where(VerificationSession.created_at < now - timedelta(days=days))).all()
    for s in old:
        db.delete(s)  # ORM delete so the cascade to results/challenges runs on every database
    audit_cutoff = now - timedelta(days=max(days, AUDIT_KEEP_DAYS_FLOOR))
    audits = db.execute(delete(AuditLog).where(AuditLog.created_at < audit_cutoff).execution_options(synchronize_session="fetch")).rowcount or 0
    if old or audits:
        audit_service.record(db, "retention.purge", details={"days": days, "verifications": len(old), "audit_logs": audits})
    db.commit()
    log.info("Retention purge: %d verification(s), %d audit entr(ies) removed (older than %d days)", len(old), audits, days)
    return {"verifications": len(old), "audit_logs": audits}
