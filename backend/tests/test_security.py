from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_is_hashed_and_verifiable():
    hashed = hash_password("my-secret-pw")
    assert hashed != "my-secret-pw"
    assert verify_password("my-secret-pw", hashed)
    assert not verify_password("wrong-pw", hashed)


def test_same_password_gets_different_hashes():
    assert hash_password("same-password") != hash_password("same-password")


def test_token_round_trip():
    token = create_access_token(42)
    assert decode_access_token(token) == 42


def test_garbage_token_is_rejected():
    assert decode_access_token("not-a-jwt") is None


def test_tampered_token_is_rejected():
    token = create_access_token(1)
    assert decode_access_token(token[:-2] + "xx") is None


def test_token_signed_with_other_secret_is_rejected():
    forged = jwt.encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        "some-other-secret-that-is-long-enough-0123456789",
        algorithm=settings.jwt_algorithm,
    )
    assert decode_access_token(forged) is None


def test_expired_token_is_rejected():
    expired = jwt.encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    assert decode_access_token(expired) is None
