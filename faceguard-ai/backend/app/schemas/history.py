"""Schemas for verification history, reports, audit logs and the model registry (mirrored in frontend/src/types/)."""
import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel

from app.models.enums import SessionMode, VerificationStatus
from app.schemas.dashboard import SpoofCategory, Totals


class HistoryItem(BaseModel):
    id: uuid.UUID
    created_at: datetime
    mode: SessionMode
    status: VerificationStatus
    spoof_type: str | None
    confidence: float | None
    face_count: int | None
    processing_ms: int | None


class HistoryPage(BaseModel):
    items: list[HistoryItem]
    total: int
    page: int
    page_size: int


class SeriesPoint(BaseModel):
    bucket: date  # first day of the day/week/month
    real: int
    fake: int
    uncertain: int
    failed: int


class StatusCount(BaseModel):
    status: VerificationStatus
    count: int


class ReportSummary(BaseModel):
    scope: Literal["own", "all"]
    period: Literal["day", "week", "month"]
    days: int
    totals: Totals
    series: list[SeriesPoint]
    status_distribution: list[StatusCount]
    spoof_categories: list[SpoofCategory]
    avg_processing_ms: float | None


class AuditItem(BaseModel):
    id: uuid.UUID
    created_at: datetime
    action: str
    user_email: str | None
    ip_address: str | None
    entity_type: str | None
    entity_id: str | None
    details: dict[str, Any] | None


class AuditPage(BaseModel):
    items: list[AuditItem]
    total: int
    page: int
    page_size: int


class EvaluationOut(BaseModel):
    id: uuid.UUID
    evaluated_at: datetime
    sample_count: int | None
    threshold: float | None
    accuracy: float | None
    precision: float | None
    recall: float | None
    f1: float | None
    roc_auc: float | None
    apcer: float | None
    bpcer: float | None
    acer: float | None
    identity_disjoint: bool | None


class ModelOut(BaseModel):
    id: uuid.UUID
    name: str
    version: str
    architecture: str
    description: str | None
    is_trained: bool
    is_active: bool
    trained_at: datetime | None
    created_at: datetime
    has_onnx: bool
    input_crop: str  # "full" (whole image) or "face" (detected face crop): how the model expects its input
    latest_evaluation: EvaluationOut | None
    blockers: list[str]  # why activation is currently refused; empty = may be activated


class ModelDetail(ModelOut):
    evaluations: list[EvaluationOut]
