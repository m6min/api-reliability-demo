from collections.abc import AsyncIterator, Generator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.redis import get_redis
from app.core.settings import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.api.dependencies import get_current_user
from app.models.user import User
from app.models.product import Product  # noqa: F401


TEST_DATABASE_NAME = "api_reliability_test"
TEST_DATABASE_URL = (
    f"{settings.DATABASE_URL.rsplit('/', maxsplit=1)[0]}"
    f"/{TEST_DATABASE_NAME}"
)


@pytest.fixture
def admin_access(client):
    """It supplies an admin identity while keeping the real permission check."""
    async def override_current_user():
        return User(id=1, is_active=True, is_admin=True)

    app.dependency_overrides[get_current_user] = override_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def redis_mock() -> AsyncMock:
    redis = AsyncMock()
    redis.eval = AsyncMock(
        return_value=[1, settings.RATE_LIMIT_WINDOW_SECONDS]
    )
    return redis


@pytest.fixture
def client(redis_mock: AsyncMock) -> Generator[TestClient, None, None]:
    db = AsyncMock(spec=AsyncSession)

    async def override_get_db():
        yield db

    async def override_get_redis():
        return redis_mock

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def repository_db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_factory() as session:
        yield session

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)

    await engine.dispose()
