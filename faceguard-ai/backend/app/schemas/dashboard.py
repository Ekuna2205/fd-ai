"""Mirror of frontend/src/types/dashboard.ts. Change both together (tests guard the key sets)."""
import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from app.models.enums import VerificationStatus


class Totals(BaseModel):
    attempts: int
    real: int
    fake: int
    uncertain: int
    failed: int  # NO_FACE + MULTIPLE_FACES + ERROR
    success_rate: float | None  # real / attempts, 0..1; null with no attempts


class DailyPoint(BaseModel):
    date: date
    real: int
    fake: int
    uncertain: int


class SpoofCategory(BaseModel):
    category: str
    count: int


class RecentItem(BaseModel):
    id: uuid.UUID
    created_at: datetime
    status: VerificationStatus
    spoof_type: str | None
    confidence: float | None


class ActiveModel(BaseModel):
    name: str
    version: str
    trained: bool
    apcer: float | None
    bpcer: float | None
    acer: float | None
    evaluated_at: datetime | None


class DashboardOverview(BaseModel):
    totals: Totals
    daily: list[DailyPoint]
    spoof_categories: list[SpoofCategory]
    recent: list[RecentItem]
    active_model: ActiveModel | None


class HealthStatus(BaseModel):
    status: Literal["ok", "degraded"]
    database: bool
    model_loaded: bool
    model_trained: bool
