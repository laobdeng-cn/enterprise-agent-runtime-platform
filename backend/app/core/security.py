from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from jwt.exceptions import InvalidTokenError as PyJWTInvalidTokenError
from pwdlib import PasswordHash

from app.core.config import settings

password_hasher = PasswordHash.recommended()


class InvalidAccessTokenError(ValueError):
    """Raised when an access token cannot be trusted."""


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_hasher.verify(password, password_hash)


def create_access_token(subject: str, username: str) -> str:
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = {
        "sub": subject,
        "username": username,
        "type": "access",
        "iat": now,
        "exp": expires_at,
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except PyJWTInvalidTokenError as exc:
        raise InvalidAccessTokenError("Invalid or expired access token") from exc

    if payload.get("type") != "access" or not payload.get("sub"):
        raise InvalidAccessTokenError("Invalid access token payload")

    return payload
