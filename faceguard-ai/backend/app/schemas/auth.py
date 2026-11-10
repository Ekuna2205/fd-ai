import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import RoleName


def validate_password_strength(v: str) -> str:
    if len(v) < 10:
        raise ValueError("Password must be at least 10 characters.")
    if len(v) > 128:
        raise ValueError("Password must be at most 128 characters.")
    if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
        raise ValueError("Password must contain at least one letter and one number.")
    return v


class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=100)
    password: str

    @field_validator("full_name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = " ".join(v.split())
        if len(v) < 2:
            raise ValueError("Enter your full name.")
        return v

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        return validate_password_strength(v)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: RoleName = Field(validation_alias="role_name")  # read from User.role_name
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None


class AuthResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int  # seconds
    refresh_token: str
    refresh_expires_in: int  # seconds
    user: UserOut


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=200)


class LogoutRequest(BaseModel):
    refresh_token: str | None = Field(default=None, max_length=200)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _password(cls, v: str) -> str:
        return validate_password_strength(v)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _password(cls, v: str) -> str:
        return validate_password_strength(v)


class ProfileUpdate(BaseModel):
    """Only the display name can be changed here. Role and status are admin-only and rejected (extra=forbid)."""

    model_config = ConfigDict(extra="forbid")
    full_name: str = Field(min_length=2, max_length=100)

    @field_validator("full_name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = " ".join(v.split())
        if len(v) < 2:
            raise ValueError("Enter your full name.")
        return v


class MessageOut(BaseModel):
    detail: str


class UserUpdate(BaseModel):
    role: RoleName | None = None
    is_active: bool | None = None


class UserList(BaseModel):
    items: list[UserOut]
    total: int
