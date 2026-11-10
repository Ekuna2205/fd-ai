from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from sqlalchemy.engine import URL
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """All configuration comes from environment variables (or backend/.env). No secrets have defaults."""

    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR.parent / ".env", BACKEND_DIR / ".env"),
        extra="ignore",
    )

    environment: str = "development"
    docs_enabled: bool = True
    log_level: str = "INFO"

    # Either set DATABASE_URL, or set the POSTGRES_* parts and the URL is assembled (and escaped) for you.
    database_url: str = ""
    postgres_user: str = "faceguard"
    postgres_password: str = ""
    postgres_db: str = "faceguard"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    jwt_secret: str = Field(..., min_length=32, description="HMAC secret, at least 32 characters")
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = Field(30, ge=5, le=1440)
    refresh_token_days: int = Field(7, ge=1, le=90)
    password_reset_minutes: int = Field(30, ge=5, le=1440)
    app_base_url: str = "http://localhost:5173"  # used to build the link in password-reset e-mails

    # Password-reset e-mail. Leave SMTP_HOST empty to disable it: the API then answers 503 instead of pretending.
    smtp_host: str = ""
    smtp_port: int = Field(587, ge=1, le=65535)
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_starttls: bool = True
    smtp_ssl: bool = False  # implicit TLS (port 465); mutually exclusive with STARTTLS

    cors_origins: str = "http://localhost:5173"
    # Comma-separated e-mails that are always administrators (promoted at sign-up / sign-in). Recovery path when the
    # first account is lost or someone else registered first.
    admin_emails: str = ""
    registration_enabled: bool = True
    rate_limit_auth_per_minute: int = Field(10, ge=0)  # 0 disables rate limiting
    rate_limit_detect_per_minute: int = Field(600, ge=0)  # live preview frames (~4/s)
    rate_limit_verify_per_minute: int = Field(30, ge=0)  # saved verifications and uploads
    rate_limit_dataset_per_minute: int = Field(300, ge=0)  # dataset image uploads and edits
    rate_limit_challenge_per_minute: int = Field(20, ge=0)
    rate_limit_collect_per_minute: int = Field(12, ge=0)  # public collection links, per IP address
    rate_limit_collect_frame_per_minute: int = Field(600, ge=0)  # live guidance frames on collection links, per IP
    collect_step_seconds: int = Field(6, ge=3, le=7)  # time allowed for each camera step before moving on
    collect_frames: int = Field(8, ge=1, le=32)  # single-face frames kept per recording  # issuing/verifying liveness challenges

    # Media limits (enforced server-side; the UI reads them from /api/face/capabilities)
    max_image_mb: int = Field(10, ge=1)
    max_video_mb: int = Field(50, ge=1)
    max_video_seconds: int = Field(30, ge=1)
    max_image_pixels: int = Field(25_000_000, ge=1_000_000)
    video_sample_frames: int = Field(16, ge=4, le=64)
    landmark_model_path: str = str(BACKEND_DIR / "app" / "assets" / "lbfmodel.yaml")
    face_detector: str = "auto"  # auto (YuNet if installed, else Haar) | yunet | haar
    yunet_model_path: str = str(BACKEND_DIR / "app" / "assets" / "face_detection_yunet_2023mar.onnx")
    upload_temp_dir: str = ""  # empty = system temp directory
    retention_days: int = Field(0, ge=0)  # 0 = keep verification records until their owner deletes them
    # Liveness inference with the active ONNX model. Scores within +/- this margin of the model's threshold are reported
    # UNCERTAIN instead of REAL/FAKE. Larger = fewer, more reliable verdicts.
    liveness_uncertainty_margin: float = Field(0.1, ge=0.0, le=0.5)
    liveness_require_quality: bool = True  # withhold REAL/FAKE when the image fails the quality checks
    liveness_min_video_frames: int = Field(3, ge=1)  # scored single-face frames a video needs for a verdict
    inference_threads: int = Field(2, ge=1, le=32)
    max_model_mb: int = Field(50, ge=1)  # ONNX upload limit on the Models page (the Nginx gateway allows 60 MB bodies)
    min_eval_samples: int = Field(200, ge=1)  # a model needs an evaluation on at least this many test samples to be activated
    data_dir: str = str(BACKEND_DIR / "data")  # dataset storage (mount a persistent volume here in production)
    challenge_ttl_seconds: int = Field(120, ge=30, le=600)
    # Single-process mode: the API also serves the built React app from this folder (frontend/dist).
    # Empty = use ../frontend/dist when it exists. Behind the Nginx gateway the folder is simply absent.
    frontend_dir: str = ""

    @field_validator("jwt_secret")
    @classmethod
    def _reject_placeholder(cls, v: str) -> str:
        if "CHANGE_ME" in v.upper():
            raise ValueError("JWT_SECRET still contains the CHANGE_ME placeholder")
        return v

    @model_validator(mode="after")
    def _build_database_url(self) -> "Settings":
        # Hosting platforms (Render, Railway, Heroku) hand out postgres:// URLs; SQLAlchemy needs the driver named.
        for prefix in ("postgres://", "postgresql://"):
            if self.database_url.startswith(prefix):
                self.database_url = "postgresql+psycopg://" + self.database_url[len(prefix):]
        if not self.database_url:
            if not self.postgres_password:
                raise ValueError("Set DATABASE_URL, or POSTGRES_PASSWORD (with the other POSTGRES_* values)")
            if "CHANGE_ME" in self.postgres_password.upper():
                raise ValueError("POSTGRES_PASSWORD still contains the CHANGE_ME placeholder")
            self.database_url = URL.create(
                "postgresql+psycopg", username=self.postgres_user, password=self.postgres_password,
                host=self.postgres_host, port=self.postgres_port, database=self.postgres_db,
            ).render_as_string(hide_password=False)
        return self

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_from)

    @model_validator(mode="after")
    def _production_guards(self) -> "Settings":
        """ENVIRONMENT=production turns on strict startup checks. Development stays permissive."""
        if self.environment.lower() == "production" and "*" in self.cors_origin_list:
            raise ValueError("CORS_ORIGINS must list explicit origins in production; '*' is not allowed")
        return self

    @property
    def frontend_path(self) -> Path | None:
        """Folder holding the built single-page app (index.html), or None when the API runs alone."""
        candidate = Path(self.frontend_dir) if self.frontend_dir else BACKEND_DIR.parent / "frontend" / "dist"
        return candidate if (candidate / "index.html").is_file() else None

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def admin_email_set(self) -> set[str]:
        return {e.strip().lower() for e in self.admin_emails.split(",") if e.strip()}

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
