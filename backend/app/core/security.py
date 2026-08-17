"""Security utilities: password hashing and JWT tokens."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from bcrypt import checkpw, gensalt, hashpw
from jwt.exceptions import PyJWTError

from app.core.config import get_settings
from app.core.exceptions import UnauthorizedError
from app.models.user import User

settings = get_settings()


def hash_password(password: str) -> str:
    """Hash plain password."""
    return hashpw(password.encode("utf-8"), gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify password against hash."""
    try:
        return checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user: User) -> str:
    """Create JWT access token."""
    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user.id),
        "is_admin": user.is_admin,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }

    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token(user: User) -> tuple[str, str, datetime]:
    """Create JWT refresh token and return token, jti, expires_at."""
    now = datetime.now(timezone.utc)
    jti = str(uuid4())
    expires_at = now + timedelta(days=settings.refresh_token_expire_days)

    payload = {
        "sub": str(user.id),
        "type": "refresh",
        "jti": jti,
        "iat": now,
        "exp": expires_at,
    }

    token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)

    return token, jti, expires_at


def decode_token(token: str, expected_type: str) -> dict:
    """Decode JWT token and validate token type."""
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
    except PyJWTError as exc:
        raise UnauthorizedError() from exc

    if payload.get("type") != expected_type:
        raise UnauthorizedError()

    return payload


def decode_access_token(token: str) -> dict:
    """Decode access token."""
    return decode_token(token, "access")


def decode_refresh_token(token: str) -> dict:
    """Decode refresh token."""
    return decode_token(token, "refresh")
