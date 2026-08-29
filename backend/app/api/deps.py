import time
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.user import User

# Выносим схемы на уровень модуля
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_prefix}/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(
    tokenUrl=f"{settings.api_v1_prefix}/auth/login",
    auto_error=False
)


async def get_current_user(
        token: Annotated[str, Depends(oauth2_scheme)],
        db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось проверить учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id_str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        user_id = int(user_id_str)
    except (JWTError, ValueError):
        raise credentials_exception

    user = await db.get(User, user_id)
    if user is None:
        raise credentials_exception
    return user


async def get_admin_user(
        current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not getattr(current_user, "is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для выполнения этого действия",
        )
    return current_user


async def optional_current_user(
        token: str | None = Depends(oauth2_scheme_optional),
        db: AsyncSession = Depends(get_db),
) -> User | None:
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id_str = payload.get("sub")
        if user_id_str is None:
            return None
        user_id = int(user_id_str)
    except (JWTError, ValueError):
        return None

    return await db.get(User, user_id)


# --- RATE LIMITER ---
_rate_limit_store = {}


def _get_client_ip(request: Request) -> str:
    """Получение реального IP с учетом прокси"""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def auth_rate_limiter(request: Request):
    client_ip = _get_client_ip(request)
    current_time = time.time()
    window_seconds = settings.rate_limit_auth_window_seconds
    max_requests = settings.rate_limit_auth_requests

    if client_ip in _rate_limit_store:
        # Очищаем старые записи
        _rate_limit_store[client_ip] = [
            t for t in _rate_limit_store[client_ip]
            if current_time - t < window_seconds
        ]
        # ИЗБАВЛЯЕМСЯ ОТ УТЕЧКИ ПАМЯТИ: удаляем пустые списки
        if not _rate_limit_store[client_ip]:
            del _rate_limit_store[client_ip]

    current_attempts = _rate_limit_store.get(client_ip, [])

    if len(current_attempts) >= max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Слишком много попыток. Попробуйте позже."
        )

    # Добавляем текущую попытку
    _rate_limit_store.setdefault(client_ip, []).append(current_time)
