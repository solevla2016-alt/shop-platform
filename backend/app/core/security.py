"""Security utilities: password hashing and JWT tokens."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from bcrypt import checkpw, gensalt, hashpw
from jwt.exceptions import PyJWTError

from app.core.config import settings
from app.core.exceptions import UnauthorizedError
from app.models.user import User


def hash_password(password: str) -> str:
    return hashpw(
        password.encode("utf-8"), gensalt()
    ).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return checkpw(
            password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "is_admin": bool(user.is_admin),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(
            minutes=settings.access_token_expire_minutes
        ),
    }
    return jwt.encode(
        payload, settings.secret_key, algorithm=settings.algorithm
    )


def create_refresh_token(user: User) -> tuple[str, str, datetime]:
    now = datetime.now(timezone.utc)
    jti = str(uuid4())
    expires_at = now + timedelta(
        days=settings.refresh_token_expire_days
    )
    payload = {
        "sub": str(user.id),
        "type": "refresh",
        "jti": jti,
        "iat": now,
        "exp": expires_at,
    }
    return (
        jwt.encode(
            payload,
            settings.secret_key,
            algorithm=settings.algorithm,
        ),
        jti,
        expires_at,
    )


def decode_token(token: str, expected_type: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
    except PyJWTError as exc:
        raise UnauthorizedError(
            "Недействительный или просроченный токен"
        ) from exc

    if payload.get("type") != expected_type:
        raise UnauthorizedError("Недействительный тип токена")

    return payload


def decode_access_token(token: str) -> dict:
    return decode_token(token, "access")


def decode_refresh_token(token: str) -> dict:
    return decode_token(token, "refresh")
