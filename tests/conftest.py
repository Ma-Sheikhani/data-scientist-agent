import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.core.database import Base, engine


@pytest.fixture(scope="session", autouse=True)
async def setup_database():
    """Create all tables once before any test starts."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Drop all tables after the entire test session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session():
    """A session that is rolled back after the test, keeping the database clean."""
    async with engine.connect() as conn:
        await conn.begin()
        session = async_sessionmaker(bind=conn, class_=AsyncSession)()
        yield session
        await conn.rollback()
