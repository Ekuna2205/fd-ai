import uuid
from collections.abc import Callable
from typing import Annotated, Any

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core import security
from app.core.errors import AuthenticationError, PermissionDenied
from app.database.session import get_db
from app.models.enums import RoleName
from app.models.user import User
from app.repositories import user_repository as users

DbSession = Annotated[Session, Depends(get_db)]
_bearer = HTTPBearer(auto_error=False, description="Paste the access_token returned by /api/auth/login.")


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def get_token_claims(
    db: DbSession, creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]
) -> dict[str, Any]:
    if creds is None:
        raise AuthenticationError("Not authenticated.")
    try:
        claims = security.decode_access_token(creds.credentials)
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Your session has expired. Sign in again.") from None
    except jwt.PyJWTError:
        raise AuthenticationError("Invalid authentication token.") from None
    if users.is_token_revoked(db, claims["jti"]):
        raise AuthenticationError("Your session has ended. Sign in again.")
    return claims


def get_current_user(db: DbSession, claims: Annotated[dict[str, Any], Depends(get_token_claims)]) -> User:
    try:
        user = users.get_by_id(db, uuid.UUID(claims["sub"]))
    except ValueError:
        raise AuthenticationError("Invalid authentication token.") from None
    if user is None or not user.is_active:
        raise AuthenticationError("Account not found or disabled.")
    if int(claims.get("pca", 0)) != security.password_epoch(user.password_changed_at):
        raise AuthenticationError("Your password was changed. Sign in again.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*allowed: RoleName) -> Callable[..., User]:
    """Role is always read from the database, never from the token, so changes apply immediately."""
    names = {r.value for r in allowed}

    def dependency(user: CurrentUser) -> User:
        if user.role.name not in names:
            raise PermissionDenied("You do not have permission to perform this action.")
        return user

    return dependency
