import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, CreatedAt, UUIDPrimaryKey
from app.models.enums import ChallengeType, FileStatus, SessionMode, SpoofType, VerificationStatus


def _enum(e: type, length: int = 24) -> Enum:
    # Stored as VARCHAR (no native PG enum) so adding values never needs a type migration.
    return Enum(e, native_enum=False, length=length, validate_strings=True)


class VerificationSession(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "verification_sessions"
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    mode: Mapped[SessionMode] = mapped_column(_enum(SessionMode), nullable=False)
    consent_given: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    challenge_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retention_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    results: Mapped[list["VerificationResult"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    challenges: Mapped[list["VerificationChallenge"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class VerificationResult(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "verification_results"
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("verification_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[VerificationStatus] = mapped_column(_enum(VerificationStatus), nullable=False)
    spoof_type: Mapped[SpoofType | None] = mapped_column(_enum(SpoofType))
    liveness_score: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)  # 0..1, null when no trained model produced it
    face_count: Mapped[int | None] = mapped_column(Integer)
    quality: Mapped[dict | None] = mapped_column(JSON)
    explanation: Mapped[str | None] = mapped_column(Text)
    model_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ai_models.id", ondelete="SET NULL"), index=True)
    model_version: Mapped[str | None] = mapped_column(String(64))
    processing_ms: Mapped[int | None] = mapped_column(Integer)

    session: Mapped[VerificationSession] = relationship(back_populates="results")

    __table_args__ = (Index("ix_verification_results_status_created_at", "status", "created_at"),)


class VerificationChallenge(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "verification_challenges"
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("verification_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    challenge_type: Mapped[ChallengeType] = mapped_column(_enum(ChallengeType), nullable=False)
    sequence_index: Mapped[int] = mapped_column(Integer, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    passed: Mapped[bool | None] = mapped_column(Boolean)  # null until evaluated

    session: Mapped[VerificationSession] = relationship(back_populates="challenges")


class UploadedFile(UUIDPrimaryKey, CreatedAt, Base):
    """Metadata only. Raw media is deleted after processing unless a retention policy says otherwise."""

    __tablename__ = "uploaded_files"
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    session_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("verification_sessions.id", ondelete="SET NULL"), index=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    storage_path: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[FileStatus] = mapped_column(_enum(FileStatus), nullable=False, default=FileStatus.PENDING)
    delete_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
