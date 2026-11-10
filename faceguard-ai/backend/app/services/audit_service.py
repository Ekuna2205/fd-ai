import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.system import AuditLog


def record(db: Session, action: str, *, user_id: uuid.UUID | None = None, ip: str | None = None,
           entity_type: str | None = None, entity_id: str | None = None, details: dict[str, Any] | None = None) -> None:
    """Adds an audit row to the current transaction (caller commits). Never pass secrets or biometric data."""
    db.add(AuditLog(user_id=user_id, action=action, ip_address=ip, entity_type=entity_type,
                    entity_id=entity_id, details=details))
