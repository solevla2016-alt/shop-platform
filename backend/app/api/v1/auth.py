"""Authentication endpoints."""
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import auth_rate_limiter, get_current_user
from app.core.config import settings
from app.core.email import send_password_reset_email
from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    UnauthorizedError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.password_reset_token import PasswordResetToken
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from app.schemas.user import UserCreate, UserOut


logger = logging.getLogger(__name__)
router = APIRouter(tags=["Auth"])


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def issue_tokens(user: User, db: AsyncSession) -> TokenResponse:
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
    dependencies=[Depends(auth_rate_limiter)],
)
async def register(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> User:
    email = str(payload.email).strip().lower()
    phone = payload.phone.strip()
    existing = await db.scalar(
        select(User).where(
            or_(User.email == email, User.phone == phone)
        )
    )

    if existing:
        message = (
            "Пользователь с таким email уже существует"
            if existing.email == email
            else "Пользователь с таким телефоном уже существует"
        )
        raise ConflictError(message)

    user = User(
        full_name=payload.full_name.strip(),
        email=email,
        phone=phone,
        password_hash=hash_password(payload.password),
    )
    db.add(user)

    try:
        await db.commit()
        await db.refresh(user)
    except Exception:
        await db.rollback()
        logger.exception("Failed to register user: %s", email)
        raise

    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(auth_rate_limiter)],
)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    identifier = payload.identifier.strip()
    user = await db.scalar(
        select(User).where(
            or_(
                User.email == identifier.lower(),
                User.phone == identifier,
            )
        )
    )

    if user is None or not verify_password(
        payload.password, user.password_hash
    ):
        raise UnauthorizedError("Неверный email, телефон или пароль")

    try:
        tokens = await issue_tokens(user, db)
        await db.commit()
        return tokens
    except Exception:
        await db.rollback()
        raise


@router.post(
    "/refresh",
    response_model=TokenResponse,
    dependencies=[Depends(auth_rate_limiter)],
)
async def refresh(
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    data = decode_refresh_token(payload.refresh_token)
    jti = data.get("jti")
    sub = data.get("sub")

    if not jti or not sub:
        raise UnauthorizedError()

    try:
        user_id = int(sub)
    except (TypeError, ValueError) as exc:
        raise UnauthorizedError() from exc

    record = await db.scalar(
        select(RefreshToken).where(
            RefreshToken.jti == jti,
            RefreshToken.user_id == user_id,
        )
    )

    if (
        record is None
        or record.revoked_at is not None
        or ensure_utc(record.expires_at) <= datetime.now(timezone.utc)
    ):
        raise UnauthorizedError(
            "Refresh token недействителен или просрочен"
        )

    user = await db.get(User, user_id)

    if user is None:
        raise UnauthorizedError()

    record.revoked_at = datetime.now(timezone.utc)
    new_access = create_access_token(user)
    new_refresh, new_jti, new_exp = create_refresh_token(user)
    db.add(
        RefreshToken(
            user_id=user.id,
            jti=new_jti,
            expires_at=new_exp,
        )
    )

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(auth_rate_limiter)],
)
async def logout(
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        data = decode_refresh_token(payload.refresh_token)
        jti = data.get("jti")
        sub = data.get("sub")

        if jti and sub:
            try:
                user_id = int(sub)
            except (TypeError, ValueError):
                user_id = None

            if user_id is not None:
                record = await db.scalar(
                    select(RefreshToken).where(
                        RefreshToken.jti == jti,
                        RefreshToken.user_id == user_id,
                    )
                )

                if record and record.revoked_at is None:
                    record.revoked_at = datetime.now(timezone.utc)
                    await db.commit()
    except UnauthorizedError:
        pass

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post(
    "/forgot-password",
    dependencies=[Depends(auth_rate_limiter)],
)
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    email = str(payload.email).strip().lower()

    user = await db.scalar(
        select(User).where(User.email == email)
    )

    # Не раскрываем существование аккаунта.
    if user is None:
        return {
            "message": (
                "Если аккаунт с таким email существует, "
                "мы отправили инструкции на почту"
            )
        }

    raw_token = secrets.token_urlsafe(32)

    now = datetime.now(timezone.utc)

    await db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.is_used.is_(False),
        )
        .values(is_used=True)
    )

    reset_record = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_reset_token(raw_token),
        expires_at=now + timedelta(
            minutes=settings.password_reset_expire_minutes
        ),
    )

    db.add(reset_record)

    try:
        # Записываем изменения в текущую транзакцию,
        # но пока НЕ делаем commit.
        await db.flush()

        # Сначала реально отправляем письмо.
        await send_password_reset_email(
            user.email,
            raw_token,
        )

        # Только после успешной отправки
        # окончательно сохраняем reset token.
        await db.commit()

    except Exception as exc:
        await db.rollback()

        logger.exception(
            "Password reset request failed "
            "for user_id=%s",
            user.id,
        )

        raise BadRequestError(
            "Не удалось отправить письмо для восстановления пароля"
        ) from exc

    return {
        "message": (
            "Если аккаунт с таким email существует, "
            "мы отправили инструкции на почту"
        )
    }


@router.post("/reset-password")
async def reset_password(
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    record = await db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hash_reset_token(
                payload.token.strip()
            ),
            PasswordResetToken.is_used.is_(False),
        )
    )

    if (
        record is None
        or ensure_utc(record.expires_at) <= datetime.now(timezone.utc)
    ):
        raise BadRequestError("Недействительная или просроченная ссылка")

    user = await db.get(User, record.user_id)

    if user is None:
        raise BadRequestError("Недействительная или просроченная ссылка")

    if verify_password(payload.new_password, user.password_hash):
        raise BadRequestError(
            "Новый пароль должен отличаться от текущего"
        )

    user.password_hash = hash_password(payload.new_password)
    record.is_used = True
    now = datetime.now(timezone.utc)

    await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return {
        "message": "Пароль успешно изменён. Все активные сессии завершены."
    }
