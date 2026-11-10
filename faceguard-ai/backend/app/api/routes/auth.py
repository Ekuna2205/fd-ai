from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response, status

from app.api.deps import CurrentUser, DbSession, client_ip, get_token_claims
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.rate_limit import auth_rate_limit
from app.schemas.auth import (AuthResponse, ChangePasswordRequest, ForgotPasswordRequest, LoginRequest, LogoutRequest,
                              MessageOut, ProfileUpdate, RefreshRequest, RegisterRequest, ResetPasswordRequest, UserOut)
from app.services import auth_service, email_service
from app.core.i18n import tr

router = APIRouter(prefix="/auth", tags=["auth"])
Limited = [Depends(auth_rate_limit)]


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED, dependencies=Limited)
def register(data: RegisterRequest, request: Request, db: DbSession) -> AuthResponse:
    """The very first account becomes Administrator; every later account starts as Viewer."""
    return auth_service.register(db, data, client_ip(request))


@router.post("/login", response_model=AuthResponse, dependencies=Limited)
def login(data: LoginRequest, request: Request, db: DbSession) -> AuthResponse:
    return auth_service.login(db, data, client_ip(request))


@router.post("/refresh", response_model=AuthResponse, dependencies=Limited)
def refresh(data: RefreshRequest, request: Request, db: DbSession) -> AuthResponse:
    """Exchanges a refresh token for a new access token and a new refresh token (the old one stops working)."""
    return auth_service.refresh(db, data.refresh_token, client_ip(request))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, db: DbSession, user: CurrentUser,
           claims: Annotated[dict[str, Any], Depends(get_token_claims)], data: LogoutRequest | None = None) -> Response:
    """Revokes the presented access token and, if given, the refresh-token family of this session."""
    auth_service.logout(db, user, claims, client_ip(request), data.refresh_token if data else None)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("/me", response_model=UserOut)
def update_me(data: ProfileUpdate, request: Request, db: DbSession, user: CurrentUser) -> UserOut:
    """Edits the caller's own display name. Role and status cannot be changed here (unknown fields are rejected)."""
    return UserOut.model_validate(auth_service.update_profile(db, user, data.full_name, client_ip(request)))


@router.post("/change-password", response_model=AuthResponse, dependencies=Limited)
def change_password(data: ChangePasswordRequest, request: Request, db: DbSession, user: CurrentUser) -> AuthResponse:
    """Needs the current password. Ends every other session and returns fresh tokens for this one."""
    return auth_service.change_password(db, user, data, client_ip(request))


@router.get("/password-reset/status", response_model=dict[str, bool])
def password_reset_status() -> dict[str, bool]:
    """Lets the UI say honestly whether e-mail reset is available on this server."""
    return {"email_reset_available": get_settings().smtp_configured}


@router.post("/forgot-password", response_model=MessageOut, status_code=status.HTTP_202_ACCEPTED, dependencies=Limited)
def forgot_password(data: ForgotPasswordRequest, request: Request, db: DbSession, tasks: BackgroundTasks) -> MessageOut:
    if not get_settings().smtp_configured:
        # Never pretend: without SMTP no e-mail can be sent. The answer is the same for every address.
        raise AppError("Password reset by e-mail is not configured on this server. Ask an administrator to reset it.", 503)
    issued = auth_service.request_password_reset(db, data.email, client_ip(request))
    if issued:
        raw, user = issued
        tasks.add_task(email_service.send_password_reset_safe, user.email, user.full_name, raw)
    return MessageOut(detail=tr("If an account exists for that address, a reset link has been sent."))


@router.post("/reset-password", response_model=MessageOut, dependencies=Limited)
def reset_password(data: ResetPasswordRequest, request: Request, db: DbSession) -> MessageOut:
    auth_service.reset_password(db, data, client_ip(request))
    return MessageOut(detail=tr("Your password has been changed. Sign in with the new password."))
