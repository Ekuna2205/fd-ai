from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.core.errors import PermissionDenied
from app.models.enums import RoleName
from app.schemas.dashboard import DashboardOverview
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview", response_model=DashboardOverview)
def overview(db: DbSession, user: CurrentUser,
             scope: Annotated[Literal["own", "all"], Query()] = "own") -> DashboardOverview:
    """Aggregates the caller's own stored results. Zeros/empty lists when there are none.

    `scope=all` is an aggregate over every user and is restricted to administrators.
    """
    if scope == "all":
        if user.role.name != RoleName.ADMINISTRATOR.value:
            raise PermissionDenied("You do not have permission to perform this action.")
        return dashboard_service.build_overview(db, None)
    return dashboard_service.build_overview(db, user.id)
