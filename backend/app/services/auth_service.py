import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import get_settings
from app.core.errors import AppError, AuthenticationError, Conflict, NotFound, PermissionDenied
from app.models.enums import RoleName
from app.models.user import PasswordResetToken, RefreshToken, RevokedToken, User
from app.repositories import user_repository as users
from app.schemas.auth import (AuthResponse, ChangePasswordRequest, LoginRequest, RegisterRequest, ResetPasswordRequest,
                              UserOut, UserUpdate)
from app.services import audit_service

_BOOTSTRAP_LOCK = 7243001


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)  # SQLite returns naive datetimes


def _issue(db: Session, user: User, family_id: str | None = None) -> AuthResponse:
    """Creates an access token plus a new refresh token and commits."""
    s = get_settings()
    token, _, exp = security.create_access_token(user.id, security.password_epoch(user.password_changed_at))
    raw, digest = security.new_opaque_token()
    now = datetime.now(UTC)
    refresh_exp = now + timedelta(days=s.refresh_token_days)
    db.add(RefreshToken(token_hash=digest, user_id=user.id, family_id=family_id or uuid.uuid4().hex, expires_at=refresh_exp))
    db.execute(delete(RefreshToken).where(RefreshToken.expires_at < now - timedelta(days=1)).execution_options(synchronize_session="fetch"))  # housekeeping
    db.commit()
    return AuthResponse(access_token=token, expires_in=int((exp - now).total_seconds()), refresh_token=raw,
                        refresh_expires_in=int((refresh_exp - now).total_seconds()), user=UserOut.model_validate(user))


def _revoke_all_refresh_tokens(db: Session, user_id: uuid.UUID) -> None:
    db.execute(update(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
               .values(revoked_at=datetime.now(UTC)).execution_options(synchronize_session="fetch"))


def _revoke_family(db: Session, family_id: str) -> None:
    db.execute(update(RefreshToken).where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
               .values(revoked_at=datetime.now(UTC)).execution_options(synchronize_session="fetch"))


def _promote_if_listed(db: Session, user: User, ip: str | None) -> None:
    """ADMIN_EMAILS: these accounts are always administrators (recovery when the first account is lost)."""
    if user.email.lower() in get_settings().admin_email_set and user.role.name != RoleName.ADMINISTRATOR.value:
        old = user.role.name
        user.role = users.get_or_create_role(db, RoleName.ADMINISTRATOR)
        audit_service.record(db, "user.role_changed", user_id=user.id, ip=ip, entity_type="user", entity_id=str(user.id),
                             details={"from": old, "to": RoleName.ADMINISTRATOR.value, "reason": "ADMIN_EMAILS"})


def register(db: Session, data: RegisterRequest, ip: str | None) -> AuthResponse:
    if db.get_bind().dialect.name == "postgresql":
        # Serialise registrations so two simultaneous first sign-ups cannot both become administrator.
        db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _BOOTSTRAP_LOCK})
    first_user = users.count_users(db) == 0
    if not first_user and not get_settings().registration_enabled:
        raise PermissionDenied("Registration is disabled. Ask an administrator to create your account.")
    email = data.email.lower()
    if users.get_by_email(db, email):
        raise Conflict("An account with this email already exists.")

    role = users.get_or_create_role(db, RoleName.ADMINISTRATOR if first_user else RoleName.VIEWER)
    user = User(email=email, full_name=data.full_name, password_hash=security.hash_password(data.password), role=role)
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise Conflict("An account with this email already exists.") from None
    audit_service.record(db, "auth.register", user_id=user.id, ip=ip, entity_type="user", entity_id=str(user.id),
                         details={"role": role.name, "bootstrap_admin": first_user})
    _promote_if_listed(db, user, ip)
    return _issue(db, user)


def login(db: Session, data: LoginRequest, ip: str | None) -> AuthResponse:
    user = users.get_by_email(db, data.email)
    ok = security.verify_password(data.password, user.password_hash if user else None)
    if not user or not ok:
        audit_service.record(db, "auth.login_failed", user_id=user.id if user else None, ip=ip)
        db.commit()
        raise AuthenticationError("Incorrect email or password.")
    if not user.is_active:
        audit_service.record(db, "auth.login_blocked", user_id=user.id, ip=ip, details={"reason": "inactive"})
        db.commit()
        raise PermissionDenied("This account is disabled. Contact an administrator.")
    if security.needs_rehash(user.password_hash):
        user.password_hash = security.hash_password(data.password)
    user.last_login_at = datetime.now(UTC)
    audit_service.record(db, "auth.login", user_id=user.id, ip=ip)
    _promote_if_listed(db, user, ip)
    return _issue(db, user)


def logout(db: Session, user: User, claims: dict[str, Any], ip: str | None, refresh_token: str | None = None) -> None:
    now = datetime.now(UTC)
    db.execute(delete(RevokedToken).where(RevokedToken.expires_at < now).execution_options(synchronize_session="fetch"))  # purge expired denylist rows
    if not users.is_token_revoked(db, claims["jti"]):
        db.add(RevokedToken(jti=claims["jti"], user_id=user.id,
                            expires_at=datetime.fromtimestamp(claims["exp"], UTC)))
    if refresh_token:  # revoke that session's whole refresh family (only if it belongs to this user)
        row = db.get(RefreshToken, security.hash_opaque_token(refresh_token))
        if row is not None and row.user_id == user.id:
            _revoke_family(db, row.family_id)
    audit_service.record(db, "auth.logout", user_id=user.id, ip=ip)
    db.commit()


def refresh(db: Session, raw_token: str, ip: str | None) -> AuthResponse:
    """Rotates a refresh token. Presenting an already-used token revokes the whole family (replay protection)."""
    row = db.get(RefreshToken, security.hash_opaque_token(raw_token))
    if row is None:
        raise AuthenticationError("Invalid refresh token. Sign in again.")
    if row.revoked_at is not None:
        _revoke_family(db, row.family_id)
        audit_service.record(db, "auth.refresh_reuse", user_id=row.user_id, ip=ip)
        db.commit()
        raise AuthenticationError("This session has ended. Sign in again.")
    if _aware(row.expires_at) <= datetime.now(UTC):
        raise AuthenticationError("Your session has expired. Sign in again.")
    user = users.get_by_id(db, row.user_id)
    if user is None or not user.is_active:
        _revoke_family(db, row.family_id)
        db.commit()
        raise AuthenticationError("Account not found or disabled.")
    row.revoked_at = datetime.now(UTC)
    return _issue(db, user, family_id=row.family_id)


def change_password(db: Session, user: User, data: ChangePasswordRequest, ip: str | None) -> AuthResponse:
    if not security.verify_password(data.current_password, user.password_hash):
        audit_service.record(db, "auth.password_change_failed", user_id=user.id, ip=ip)
        db.commit()
        raise AppError("Your current password is incorrect.", 400)
    if data.current_password == data.new_password:
        raise AppError("Choose a password different from the current one.", 400)
    user.password_hash = security.hash_password(data.new_password)
    user.password_changed_at = datetime.now(UTC)
    _revoke_all_refresh_tokens(db, user.id)  # every other device must sign in again
    audit_service.record(db, "auth.password_change", user_id=user.id, ip=ip)
    return _issue(db, user)  # this device keeps a fresh session


def request_password_reset(db: Session, email: str, ip: str | None) -> tuple[str, User] | None:
    """Returns (raw_token, user) when a mail should be sent, else None. The caller answers identically either way."""
    user = users.get_by_email(db, email)
    if user is None or not user.is_active:
        audit_service.record(db, "auth.reset_requested_unknown", ip=ip)
        db.commit()
        return None
    db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id).execution_options(synchronize_session="fetch"))  # one live token per user
    raw, digest = security.new_opaque_token()
    db.add(PasswordResetToken(token_hash=digest, user_id=user.id,
                              expires_at=datetime.now(UTC) + timedelta(minutes=get_settings().password_reset_minutes)))
    audit_service.record(db, "auth.reset_requested", user_id=user.id, ip=ip)
    db.commit()
    return raw, user


def reset_password(db: Session, data: ResetPasswordRequest, ip: str | None) -> None:
    bad = AppError("This reset link is invalid or has expired. Request a new one.", 400)
    row = db.get(PasswordResetToken, security.hash_opaque_token(data.token))
    now = datetime.now(UTC)
    if row is None or row.used_at is not None or _aware(row.expires_at) <= now:
        raise bad
    user = users.get_by_id(db, row.user_id)
    if user is None or not user.is_active:
        raise bad
    row.used_at = now
    user.password_hash = security.hash_password(data.new_password)
    user.password_changed_at = now
    _revoke_all_refresh_tokens(db, user.id)
    audit_service.record(db, "auth.password_reset", user_id=user.id, ip=ip)
    db.commit()


def update_profile(db: Session, user: User, full_name: str, ip: str | None) -> User:
    if full_name != user.full_name:
        audit_service.record(db, "auth.profile_update", user_id=user.id, ip=ip, entity_type="user", entity_id=str(user.id))
        user.full_name = full_name
        db.commit()
    return user


def update_user(db: Session, actor: User, user_id: uuid.UUID, data: UserUpdate, ip: str | None) -> User:
    target = users.get_by_id(db, user_id)
    if target is None:
        raise NotFound("User not found.")
    if target.id == actor.id:
        raise AppError("You cannot change your own role or status. Ask another administrator.", 400)
    changes: dict[str, Any] = {}
    if data.role is not None and data.role.value != target.role.name:
        changes["role"] = {"from": target.role.name, "to": data.role.value}
        target.role = users.get_or_create_role(db, data.role)
    if data.is_active is not None and data.is_active != target.is_active:
        changes["is_active"] = data.is_active
        target.is_active = data.is_active
    if changes:
        audit_service.record(db, "user.update", user_id=actor.id, ip=ip, entity_type="user",
                             entity_id=str(target.id), details=changes)
        db.commit()
    return target


def admin_reset_link(db: Session, actor: User, user_id: uuid.UUID, ip: str | None, *, sign_out: bool) -> dict:
    """An administrator creates a one-time password-reset link for another user and hands it over out of band
    (works without SMTP). The administrator never learns or sets the password. Any earlier link stops working."""
    target = users.get_by_id(db, user_id)
    if target is None:
        raise NotFound("User not found.")
    if target.id == actor.id:
        raise AppError("Use Settings to change your own password.", 400)
    if not target.is_active:
        raise AppError("This account is disabled. Enable it before creating a reset link.", 400)
    db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == target.id)
               .execution_options(synchronize_session="fetch"))
    raw, digest = security.new_opaque_token()
    expires = datetime.now(UTC) + timedelta(minutes=get_settings().password_reset_minutes)
    db.add(PasswordResetToken(token_hash=digest, user_id=target.id, expires_at=expires))
    if sign_out:
        _revoke_all_refresh_tokens(db, target.id)
    audit_service.record(db, "user.reset_link_created", user_id=actor.id, ip=ip, entity_type="user",
                         entity_id=str(target.id), details={"signed_out": sign_out})  # never the token itself
    db.commit()
    return {"path": f"/reset-password?token={raw}", "expires_at": expires, "signed_out": sign_out}
