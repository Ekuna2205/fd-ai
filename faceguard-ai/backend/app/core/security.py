import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings

_hasher = PasswordHasher()  # Argon2id with library defaults
# Used to spend comparable time when the e-mail is unknown, so login timing does not reveal accounts.
_DUMMY_HASH = _hasher.hash("faceguard-timing-equalizer")
ISSUER = "faceguard-ai"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def password_epoch(changed_at: datetime | None) -> int:
    """Millisecond stamp of the last password change (0 if never). Embedded in tokens so a change kills older tokens."""
    if changed_at is None:
        return 0
    if changed_at.tzinfo is None:  # SQLite returns naive datetimes
        changed_at = changed_at.replace(tzinfo=UTC)
    return int(changed_at.timestamp() * 1000)


def create_access_token(user_id: uuid.UUID, pw_epoch: int = 0) -> tuple[str, str, datetime]:
    """Returns (token, jti, expires_at)."""
    s = get_settings()
    now = datetime.now(UTC)
    exp = now + timedelta(minutes=s.access_token_minutes)
    jti = uuid.uuid4().hex
    payload: dict[str, Any] = {"sub": str(user_id), "jti": jti, "iat": now, "exp": exp, "iss": ISSUER, "pca": pw_epoch}
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm), jti, exp


def decode_access_token(token: str) -> dict[str, Any]:
    """Raises jwt.PyJWTError on any problem (expired, bad signature, wrong issuer, missing claims)."""
    s = get_settings()
    return jwt.decode(
        token, s.jwt_secret, algorithms=[s.jwt_algorithm], issuer=ISSUER,
        options={"require": ["sub", "jti", "exp", "iat"]},
    )


def new_opaque_token() -> tuple[str, str]:
    """Returns (token_for_the_client, sha256_hex_for_the_database). The raw token is never stored."""
    raw = secrets.token_urlsafe(48)
    return raw, hash_opaque_token(raw)


def hash_opaque_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
