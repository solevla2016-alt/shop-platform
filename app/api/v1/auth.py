from fastapi import APIRouter, Depends, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, Token
from app.schemas.user import UserCreate, UserOut

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register user",
)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)):
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
    response_model=Token,
    summary="Login by email or phone",
)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
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

    return Token(access_token=create_access_token(user))