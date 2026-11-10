"""Liveness availability as shown to users. The actual inference lives in services/inference.py."""
from sqlalchemy.orm import Session

from app.schemas.face import LivenessInfo
from app.services import inference
from app.core.i18n import tr


def availability(db: Session) -> LivenessInfo:
    active, reason = inference.load_active(db)
    if active is None:
        return LivenessInfo(available=False, reason=tr(reason), model=None)
    return LivenessInfo(available=True, reason=None, model=active.label)
