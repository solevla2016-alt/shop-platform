"""FastAPI dependencies for authentication and authorization."""
from __future__ import annotations
from collections import defaultdict, deque
from time import monotonic
from typing import Annotated
from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.exceptions import ForbiddenError, TooManyRequestsError, UnauthorizedError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_prefix}/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_prefix}/auth/login", auto_error=False)

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: AsyncSession = Depends(get_db)) -> User:
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except (UnauthorizedError, KeyError, TypeError, ValueError) as exc:
        raise UnauthorizedError("Не удалось проверить учетные данные") from exc
    user = await db.get(User, user_id)
    if user is None:
        raise UnauthorizedError("Не удалось проверить учетные данные")
    return user

async def get_admin_user(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    if not current_user.is_admin:
        raise ForbiddenError("Недостаточно прав для выполнения этого действия")
    return current_user

async def optional_current_user(token: Annotated[str | None, Depends(oauth2_scheme_optional)], db: AsyncSession = Depends(get_db)) -> User | None:
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except (UnauthorizedError, KeyError, TypeError, ValueError):
        return None
    return await db.get(User, user_id)

_rate_limit_store: dict[str, deque[float]] = defaultdict(deque)

def _get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"

async def auth_rate_limiter(request: Request) -> None:
    client_ip = _get_client_ip(request)
    now = monotonic()
    window = _rate_limit_store[client_ip]
    while window and now - window[0] >= settings.rate_limit_auth_window_seconds:
        window.popleft()
    if len(window) >= settings.rate_limit_auth_requests:
        raise TooManyRequestsError("Слишком много попыток. Попробуйте позже.")
    window.append(now)
    if len(_rate_limit_store) > 10_000:
        stale = [key for key, values in _rate_limit_store.items() if not values]
        for key in stale:
            del _rate_limit_store[key]
