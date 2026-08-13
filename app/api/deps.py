from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise UnauthorizedError()

    if credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise UnauthorizedError()

    payload = decode_access_token(credentials.credentials)
    user_id_raw = payload.get("sub")

    if user_id_raw is None:
        raise UnauthorizedError()

    try:
        user_id = int(user_id_raw)
    except ValueError as exc:
        raise UnauthorizedError() from exc

    user = await db.get(User, user_id)
    if user is None:
        raise UnauthorizedError()

    return user


async def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise ForbiddenError()
    return current_user