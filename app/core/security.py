from datetime import datetime, timedelta, timezone

import jwt
from bcrypt import checkpw, gensalt, hashpw
from jwt.exceptions import PyJWTError

from app.core.config import get_settings
from app.core.exceptions import UnauthorizedError
from app.models.user import User

settings = get_settings()


def hash_password(password: str) -> str:
    return hashpw(password.encode("utf-8"), gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "is_admin": user.is_admin,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
    except PyJWTError as exc:
        raise UnauthorizedError() from exc