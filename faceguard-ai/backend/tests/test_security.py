import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core import security
from app.core.config import get_settings


def test_password_is_hashed_with_argon2_and_verifies():
    h = security.hash_password("Correct-horse-9")
    assert h.startswith("$argon2id$") and "Correct-horse-9" not in h
    assert security.verify_password("Correct-horse-9", h)
    assert not security.verify_password("wrong-password-1", h)


def test_unknown_user_never_verifies():
    assert security.verify_password("faceguard-timing-equalizer", None) is False


def test_token_roundtrip_and_claims():
    uid = uuid.uuid4()
    token, jti, exp = security.create_access_token(uid)
    claims = security.decode_access_token(token)
    assert claims["sub"] == str(uid) and claims["jti"] == jti
    assert exp > datetime.now(UTC)


def test_expired_and_foreign_tokens_are_rejected():
    s = get_settings()
    past = datetime.now(UTC) - timedelta(minutes=1)
    expired = jwt.encode({"sub": "x", "jti": "j", "iat": past - timedelta(hours=1), "exp": past, "iss": security.ISSUER},
                         s.jwt_secret, algorithm="HS256")
    with pytest.raises(jwt.ExpiredSignatureError):
        security.decode_access_token(expired)
    forged = jwt.encode({"sub": "x", "jti": "j", "iat": datetime.now(UTC), "exp": datetime.now(UTC) + timedelta(hours=1),
                         "iss": security.ISSUER}, "a" * 40, algorithm="HS256")
    with pytest.raises(jwt.InvalidSignatureError):
        security.decode_access_token(forged)
    unsigned = jwt.encode({"sub": "x"}, None, algorithm="none")
    with pytest.raises(jwt.PyJWTError):
        security.decode_access_token(unsigned)
