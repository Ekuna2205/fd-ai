from fastapi import APIRouter

from app.api.deps import DbSession
from app.schemas.dashboard import HealthStatus
from app.services import health_service

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthStatus)
def health(db: DbSession) -> HealthStatus:
    """Public. Reports `degraded` (HTTP 200) when the database is unreachable."""
    return health_service.check(db)
