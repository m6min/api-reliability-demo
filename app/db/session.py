from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..core.settings import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo = settings.SQL_ECHO,
    pool_pre_ping=True,
    pool_recycle=900,
    pool_timeout=120
)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_db() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session