import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, CreatedAt, Timestamps, UUIDPrimaryKey
from app.models.enums import DatasetSource, DataSplit, SampleLabel
from app.models.verification import _enum


class Dataset(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "datasets"
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source: Mapped[DatasetSource] = mapped_column(_enum(DatasetSource), nullable=False)
    label_studio_project_id: Mapped[int | None] = mapped_column(Integer)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    samples: Mapped[list["DatasetSample"]] = relationship(back_populates="dataset", cascade="all, delete-orphan")


class DatasetSample(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "dataset_samples"
    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    external_id: Mapped[str | None] = mapped_column(String(100))  # e.g. Label Studio task id
    uri: Mapped[str] = mapped_column(String(1000), nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    label: Mapped[SampleLabel] = mapped_column(_enum(SampleLabel), nullable=False)
    split: Mapped[DataSplit | None] = mapped_column(_enum(DataSplit))
    extra: Mapped[dict | None] = mapped_column(JSON)

    dataset: Mapped[Dataset] = relationship(back_populates="samples")

    __table_args__ = (
        UniqueConstraint("dataset_id", "external_id", name="uq_dataset_samples_dataset_external"),
        Index("ix_dataset_samples_dataset_label", "dataset_id", "label"),
    )


class AIModel(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "ai_models"
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    architecture: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # False for baseline/untrained weights. The UI and API must always surface this.
    is_trained: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    training_dataset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("datasets.id", ondelete="SET NULL"))
    trained_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checkpoint_path: Mapped[str | None] = mapped_column(String(500))
    onnx_path: Mapped[str | None] = mapped_column(String(500))
    # How the model expects its input: {"crop": "full" | "face", "face_margin": 0.4}. Null = full image (the
    # training pipeline's default). The input size is read from the ONNX file itself.
    preprocessing: Mapped[dict | None] = mapped_column(JSON)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    evaluations: Mapped[list["ModelEvaluation"]] = relationship(back_populates="model", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_ai_models_name_version"),
        # At most one active model: a unique index restricted to the active rows.
        Index("uq_ai_models_single_active", "is_active", unique=True,
              postgresql_where=is_active.is_(true()), sqlite_where=is_active.is_(true())),
    )


class ModelEvaluation(UUIDPrimaryKey, CreatedAt, Base):
    """Metrics are stored exactly as measured; ratios in 0..1. Nothing here is ever pre-filled."""

    __tablename__ = "model_evaluations"
    model_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ai_models.id", ondelete="CASCADE"), nullable=False, index=True)
    dataset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("datasets.id", ondelete="SET NULL"))
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sample_count: Mapped[int | None] = mapped_column(Integer)
    threshold: Mapped[float | None] = mapped_column(Float)
    accuracy: Mapped[float | None] = mapped_column(Float)
    precision: Mapped[float | None] = mapped_column(Float)
    recall: Mapped[float | None] = mapped_column(Float)
    f1: Mapped[float | None] = mapped_column(Float)
    roc_auc: Mapped[float | None] = mapped_column(Float)
    apcer: Mapped[float | None] = mapped_column(Float)
    bpcer: Mapped[float | None] = mapped_column(Float)
    acer: Mapped[float | None] = mapped_column(Float)
    report: Mapped[dict | None] = mapped_column(JSON)

    model: Mapped[AIModel] = relationship(back_populates="evaluations")
