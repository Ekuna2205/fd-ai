from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.api.deps import DbSession, require_roles
from app.models.enums import RoleName
from app.models.system import AuditLog
from app.models.user import User
from app.schemas.history import AuditItem, AuditPage

router = APIRouter(prefix="/admin", tags=["admin"])
AdminUser = Annotated[User, Depends(require_roles(RoleName.ADMINISTRATOR))]


@router.get("/audit-logs", response_model=AuditPage)
def audit_logs(db: DbSession, _: AdminUser, action: str | None = Query(None, max_length=64),
               page: int = Query(1, ge=1, le=100_000), page_size: int = Query(25, ge=1, le=100)) -> AuditPage:
    """Security events (who did what, when, from which IP). Contains no biometric content or secrets."""
    stmt = select(AuditLog, User.email).outerjoin(User, User.id == AuditLog.user_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = db.execute(stmt.order_by(AuditLog.created_at.desc(), AuditLog.id).limit(page_size).offset((page - 1) * page_size)).all()
    items = [AuditItem(id=a.id, created_at=a.created_at, action=a.action, user_email=email, ip_address=a.ip_address,
                       entity_type=a.entity_type, entity_id=a.entity_id, details=a.details) for a, email in rows]
    return AuditPage(items=items, total=total, page=page, page_size=page_size)
