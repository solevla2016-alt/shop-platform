import os
import time

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only-1234567890")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
os.environ.setdefault("RATE_LIMIT_AUTH_REQUESTS", "100")
os.environ.setdefault("LOG_LEVEL", "WARNING")

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool  # noqa: E402

from app.core.security import create_access_token, hash_password  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.category import Category  # noqa: E402
from app.models.product import Product  # noqa: E402
from app.models.user import User  # noqa: E402


@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = create_async_engine(
        "sqlite+aiosqlite:///./test.db",
        poolclass=NullPool,
    )

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=eng,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_factory() as session:
        session.add(
            Category(
                name="Test Category",
                slug="test-category",
                description="Test",
                icon="🌿",
            )
        )
        await session.commit()

    yield eng

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine):
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def regular_user(client, db_session):
    timestamp = int(time.time() * 1000)

    user = User(
        email=f"test_{timestamp}@example.com",
        phone=f"+7999{timestamp % 10000000:07d}",
        full_name="Test User",
        password_hash=hash_password("Password123!"),
        is_admin=False,
    )

    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    return user


@pytest_asyncio.fixture
async def second_user(client, db_session):
    timestamp = int(time.time() * 1000)

    user = User(
        email=f"second_{timestamp}@example.com",
        phone=f"+7998{timestamp % 10000000:07d}",
        full_name="Second User",
        password_hash=hash_password("Password123!"),
        is_admin=False,
    )

    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    return user


@pytest_asyncio.fixture
async def admin_user(client, db_session):
    timestamp = int(time.time() * 1000)

    user = User(
        email=f"admin_{timestamp}@example.com",
        phone=f"+7999{(timestamp + 1) % 10000000:07d}",
        full_name="Admin User",
        password_hash=hash_password("AdminPass123!"),
        is_admin=True,
    )

    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    return user


@pytest_asyncio.fixture
async def user_token(regular_user):
    return create_access_token(user=regular_user)


@pytest_asyncio.fixture
async def admin_token(admin_user):
    return create_access_token(user=admin_user)


@pytest_asyncio.fixture
async def auth_headers(user_token):
    return {
        "Authorization": f"Bearer {user_token}"
    }


@pytest_asyncio.fixture
async def admin_headers(admin_token):
    return {
        "Authorization": f"Bearer {admin_token}"
    }


@pytest_asyncio.fixture
async def second_user_headers(second_user):
    token = create_access_token(user=second_user)

    return {
        "Authorization": f"Bearer {token}"
    }


@pytest_asyncio.fixture
async def test_product(client, db_session):
    timestamp = int(time.time() * 1000)

    product = Product(
        name=f"Test Product {timestamp}",
        price=1000,
        is_active=True,
        category_id=1,
        sku=f"TEST-PRODUCT-{timestamp}",
    )

    db_session.add(product)
    await db_session.commit()
    await db_session.refresh(product)

    return product
