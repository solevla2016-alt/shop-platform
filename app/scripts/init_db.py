import asyncio

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import AsyncSessionLocal, engine
from app.models import Cart, CartItem, Product, User

settings = get_settings()


async def create_admin() -> None:
    if not all(
        [
            settings.admin_email,
            settings.admin_password,
            settings.admin_phone,
            settings.admin_full_name,
        ]
    ):
        return

    async with AsyncSessionLocal() as session:
        exists = await session.scalar(
            select(User.id).where(User.email == settings.admin_email.lower())
        )

        if exists:
            return

        admin = User(
            full_name=settings.admin_full_name,
            email=settings.admin_email.lower(),
            phone=settings.admin_phone,
            hashed_password=hash_password(settings.admin_password),
            is_admin=True,
        )

        session.add(admin)
        await session.commit()


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await create_admin()
    print("Database initialized.")


if __name__ == "__main__":
    asyncio.run(main())