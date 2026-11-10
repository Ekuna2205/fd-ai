"""Importing this package registers every table on Base.metadata (needed by Alembic)."""
from app.models.ai import AIModel, Dataset, DatasetSample, ModelEvaluation
from app.models.system import AuditLog, SystemSetting
from app.models.user import PasswordResetToken, RefreshToken, RevokedToken, Role, User
from app.models.verification import UploadedFile, VerificationChallenge, VerificationResult, VerificationSession

__all__ = [
    "AIModel", "AuditLog", "PasswordResetToken", "RefreshToken", "Dataset", "DatasetSample", "ModelEvaluation", "RevokedToken", "Role",
    "SystemSetting", "UploadedFile", "User", "VerificationChallenge", "VerificationResult", "VerificationSession",
]
