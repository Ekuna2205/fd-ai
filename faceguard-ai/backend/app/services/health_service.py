import logging

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.ai import AIModel
from app.schemas.dashboard import HealthStatus

log = logging.getLogger("faceguard.health")


def _model_loads(db: Session) -> bool:
    from app.services import inference
    try:
        return inference.load_active(db)[0] is not None
    except Exception:  # noqa: BLE001 - health must never fail because of a model problem
        log.exception("Model check failed")
        return False


def check(db: Session) -> HealthStatus:
    try:
        db.execute(text("SELECT 1"))
        database = True
    except Exception:  # noqa: BLE001 - any failure means "degraded", details go to the log
        log.exception("Database health check failed")
        return HealthStatus(status="degraded", database=False, model_loaded=False, model_trained=False)
    trained = db.scalar(select(AIModel.is_trained).where(AIModel.is_active.is_(True)))
    return HealthStatus(
        status="ok",
        database=database,
        model_loaded=_model_loads(db),  # True only when the active model really loads in ONNX Runtime
        model_trained=bool(trained),
    )
