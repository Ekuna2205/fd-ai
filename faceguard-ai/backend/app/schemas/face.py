"""Mirror of frontend/src/types/face.ts. Coordinates are normalised to 0..1 of the analysed image."""
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.models.enums import SessionMode, VerificationStatus


class Box(BaseModel):
    x: float
    y: float
    w: float
    h: float


class Face(BaseModel):
    box: Box
    landmarks: list[tuple[float, float]] | None  # 68 points (iBUG order) or null if the landmark model is unavailable
    roll_degrees: float | None


class QualityCheck(BaseModel):
    name: str
    label: str
    value: float | None
    ok: bool
    message: str | None  # user-facing hint when the check fails


class Quality(BaseModel):
    ready: bool  # all checks passed
    checks: list[QualityCheck]


class ImageInfo(BaseModel):
    width: int
    height: int


class DetectorInfo(BaseModel):
    name: str
    landmarks: bool


class DetectionOut(BaseModel):
    image: ImageInfo
    face_count: int
    faces: list[Face]
    quality: Quality | None  # only assessed when exactly one face is present
    guidance: list[str]
    detector: DetectorInfo
    processing_ms: int


class LivenessInfo(BaseModel):
    available: bool
    reason: str | None
    model: str | None = None  # "name vX" of the model used for decisions, when available


class LivenessScore(BaseModel):
    """What the model measured for this sample. Present only when an active model scored it."""
    model: str
    bona_fide_score: float  # P(bona fide), 0..1; mean over frames for videos
    threshold: float
    uncertainty_margin: float
    frames_scored: int  # 1 for images


class VideoSummary(BaseModel):
    frames_analyzed: int
    frames_single_face: int
    frames_no_face: int
    frames_multiple_faces: int
    duration_seconds: float | None
    face_presence_ratio: float
    quality_pass_ratio: float | None
    position_jitter: float | None  # std of face centre, fraction of frame size
    size_variation: float | None  # coefficient of variation of face width


class VerificationOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    mode: SessionMode
    status: VerificationStatus
    spoof_type: str | None
    confidence: float | None
    face_count: int | None
    quality: Quality | None
    video: VideoSummary | None
    explanation: str | None
    model_version: str | None
    processing_ms: int | None
    liveness: LivenessInfo
    score: LivenessScore | None


class Limits(BaseModel):
    max_image_mb: int
    max_video_mb: int
    max_video_seconds: int
    image_types: list[str]
    video_types: list[str]


class Capabilities(BaseModel):
    detector: DetectorInfo
    liveness: LivenessInfo
    limits: Limits
    consent_required: Literal[True] = True
