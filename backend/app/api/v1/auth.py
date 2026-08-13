"""Authentication endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import auth_rate_limiter, get_current_user
from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.auth_token import RefreshToken
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse
from app.schemas.user import UserCreate, UserOut

router = APIRouter(prefix="/auth", tags=["Auth"])


def ensure_utc(value: datetime) -> datetime:
    """Convert datetime to UTC-aware datetime."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def issue_tokens(user: User, db: AsyncSession) -> TokenResponse:
    """Issue access and refresh tokens."""
    access_token = create_access_token(user)
    refresh_token, jti, expires_at = create_refresh_token(user)

    db.add(
        RefreshToken(
            user_id=user.id,
            jti=jti,
            expires_at=expires_at,
        )
    )
    await db.flush()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register user",
    dependencies=[Depends(auth_rate_limiter)],
)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register a new user."""
    email = payload.email.lower()
    phone = payload.phone

    existing_user_id = await db.scalar(
        select(User.id).where(
            or_(User.email == email, User.phone == phone),
        )
    )

    if existing_user_id:
        raise ConflictError("User with this email or phone already exists")

    user = User(
        full_name=payload.full_name,
        email=email,
        phone=phone,
        hashed_password=hash_password(payload.password),
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login by email or phone",
    dependencies=[Depends(auth_rate_limiter)],
)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate user and issue tokens."""
    identifier = payload.identifier.strip()

    user = await db.scalar(
        select(User).where(
            or_(
                User.email == identifier.lower(),
                User.phone == identifier,
            )
        )
    )

    if user is None or not verify_password(payload.password, user.hashed_password):
        raise UnauthorizedError()

    tokens = await issue_tokens(user, db)
    await db.commit()

    return tokens


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    dependencies=[Depends(auth_rate_limiter)],
)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Rotate refresh token and issue new token pair."""
    payload_data = decode_refresh_token(payload.refresh_token)

    jti = payload_data.get("jti")
    sub = payload_data.get("sub")

    if not jti or not sub:
        raise UnauthorizedError()

    try:
        user_id = int(sub)
    except ValueError as exc:
        raise UnauthorizedError() from exc

    token_record = await db.scalar(
        select(RefreshToken).where(
            RefreshToken.jti == jti,
            RefreshToken.user_id == user_id,
        )
    )

    if token_record is None or token_record.revoked_at is not None:
        raise UnauthorizedError()

    if ensure_utc(token_record.expires_at) < datetime.now(timezone.utc):
        raise UnauthorizedError()

    user = await db.get(User, user_id)

    if user is None:
        raise UnauthorizedError()

    token_record.revoked_at = datetime.now(timezone.utc)

    new_access_token = create_access_token(user)
    new_refresh_token, new_jti, new_expires_at = create_refresh_token(user)

    db.add(
        RefreshToken(
            user_id=user.id,
            jti=new_jti,
            expires_at=new_expires_at,
        )
    )

    await db.commit()

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout refresh token",
    dependencies=[Depends(auth_rate_limiter)],
)
async def logout(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Revoke refresh token."""
    try:
        payload_data = decode_refresh_token(payload.refresh_token)
    except UnauthorizedError:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    jti = payload_data.get("jti")
    sub = payload_data.get("sub")

    if not jti or not sub:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    try:
        user_id = int(sub)
    except ValueError:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    token_record = await db.scalar(
        select(RefreshToken).where(
            RefreshToken.jti == jti,
            RefreshToken.user_id == user_id,
        )
    )

    if token_record and token_record.revoked_at is None:
        token_record.revoked_at = datetime.now(timezone.utc)
        await db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/me",
    response_model=UserOut,
    summary="Current user profile",
)
async def me(user: User = Depends(get_current_user)):
    """Return current authenticated user."""
    return user