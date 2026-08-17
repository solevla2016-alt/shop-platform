import os

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine # noqa: E402
from sqlalchemy.pool import NullPool # noqa: E402

from app.core.security import create_access_token, hash_password # noqa: E402
from app.db.base import Base # noqa: E402
from app.db.session import get_db # noqa: E402
from app.main import app # noqa: E402
from app.models.product import Product # noqa: E402
from app.models.user import User # noqa: E402

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=NullPool,
)

TestingSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
)


async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(autouse=True)
async def prepare_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _create_user(
    full_name: str = "Test User",
    email: str = "user@example.com",
    phone: str = "+79991234567",
    password: str = "Password$",
    is_admin: bool = False,
) -> User:
    async with TestingSessionLocal() as session:
        user = User(
            full_name=full_name,
            email=email.lower(),
            phone=phone,
            hashed_password=hash_password(password),
            is_admin=is_admin,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def _create_product(
    name: str = "Test Product",
    price: int = 100,
    is_active: bool = True,
) -> Product:
    async with TestingSessionLocal() as session:
        product = Product(name=name, price=price, is_active=is_active)
        session.add(product)
        await session.commit()
        await session.refresh(product)
        return product


@pytest.fixture
def create_user():
    return _create_user


@pytest.fixture
def create_product():
    return _create_product


@pytest.fixture
def access_token_for():
    return create_access_token


@pytest.fixture
def auth_headers():
    def _headers(token: str):
        return {"Authorization": f"Bearer {token}"}

    return _headers
