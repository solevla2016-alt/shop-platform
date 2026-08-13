"""Create initial admin user."""

import asyncio

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.user import User

settings = get_settings()


async def create_admin() -> None:
    """Create admin user if configured in environment."""
    if not all(
        [
            settings.admin_email,
            settings.admin_password,
            settings.admin_phone,
            settings.admin_full_name,
        ]
    ):
        print("Admin credentials are not fully configured. Skipping admin creation.")
        return

    async with AsyncSessionLocal() as session:
        exists = await session.scalar(
            select(User.id).where(User.email == settings.admin_email.lower())
        )

        if exists:
            print("Admin already exists.")
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

        print(f"Admin created: {settings.admin_email}")


async def main() -> None:
    """Script entrypoint."""
    await create_admin()


if __name__ == "__main__":
    asyncio.run(main())