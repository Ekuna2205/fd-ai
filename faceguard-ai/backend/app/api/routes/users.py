import uuid
from typing import Annotated

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from app.api.deps import DbSession, client_ip, require_roles
from app.models.enums import RoleName
from app.models.user import User
from app.repositories import user_repository as users
from app.schemas.auth import UserList, UserOut, UserUpdate
from app.services import auth_service

router = APIRouter(prefix="/users", tags=["users"])
AdminUser = Annotated[User, Depends(require_roles(RoleName.ADMINISTRATOR))]


@router.get("", response_model=UserList)
def list_users(db: DbSession, _: AdminUser, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)) -> UserList:
    items, total = users.list_users(db, limit, offset)
    return UserList(items=[UserOut.model_validate(u) for u in items], total=total)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: uuid.UUID, data: UserUpdate, request: Request, db: DbSession, actor: AdminUser) -> UserOut:
    return UserOut.model_validate(auth_service.update_user(db, actor, user_id, data, client_ip(request)))


class ResetLinkRequest(BaseModel):
    sign_out: bool = False  # also end the user's sessions on every device


class ResetLinkOut(BaseModel):
    path: str  # "/reset-password?token=...": the UI prefixes its own origin
    expires_at: datetime
    signed_out: bool


@router.post("/{user_id}/reset-link", response_model=ResetLinkOut)
def reset_link(user_id: uuid.UUID, data: ResetLinkRequest, request: Request, db: DbSession, actor: AdminUser) -> ResetLinkOut:
    """One-time password-reset link for another user, shown once to the administrator. No SMTP needed."""
    return ResetLinkOut(**auth_service.admin_reset_link(db, actor, user_id, client_ip(request), sign_out=data.sign_out))
