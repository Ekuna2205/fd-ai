from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, Response

from app.api.deps import CurrentUser, DbSession, client_ip, require_roles
from app.core.errors import PermissionDenied
from app.models.enums import RoleName
from app.schemas.history import ReportSummary
from app.services import audit_service, report_service

router = APIRouter(prefix="/reports", tags=["reports"])
Period = Literal["day", "week", "month"]


def _build(db, user, scope: str, period: Period, days: int) -> ReportSummary:
    if scope == "all" and user.role.name != RoleName.ADMINISTRATOR.value:
        raise PermissionDenied("Only administrators can view the all-users aggregate.")
    return report_service.build(db, None if scope == "all" else user.id, scope=scope, period=period, days=days)


@router.get("/summary", response_model=ReportSummary)
def summary(db: DbSession, user: CurrentUser, period: Period = "day", days: int = Query(30, ge=1, le=365),
            scope: Literal["own", "all"] = "own") -> ReportSummary:
    """Your own statistics by default. `scope=all` (administrators) returns aggregate counts only."""
    return _build(db, user, scope, period, days)


@router.get("/export")
def export(request: Request, db: DbSession, user: CurrentUser, period: Period = "day",
           days: int = Query(30, ge=1, le=365), scope: Literal["own", "all"] = "own") -> Response:
    rep = _build(db, user, scope, period, days)
    audit_service.record(db, "report.export", user_id=user.id, ip=client_ip(request), details={"scope": scope, "period": period})
    db.commit()
    return Response(report_service.to_csv(rep), media_type="text/csv; charset=utf-8", headers={
        "Content-Disposition": 'attachment; filename="faceguard-report.csv"', "Cache-Control": "private, no-store"})
