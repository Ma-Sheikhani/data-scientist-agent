import os

import pytest
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

from api.core.database import Base, engine


@pytest.fixture(scope="session", autouse=True)
async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Optionally drop tables after all tests
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# Declare containers as session‑scoped so they are started once and reused for all tests.
@pytest.fixture(scope="session")
def postgres():
    # Use the same image as in docker-compose for consistency
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
def redis():
    with RedisContainer("redis:7-alpine") as rd:
        yield rd


@pytest.fixture(scope="session", autouse=True)
def set_test_env(postgres, redis):
    """Override environment variables so the app uses test containers."""
    # Convert the Postgres URL to asyncpg format
    pg_url = postgres.get_connection_url()
    asyncpg_url = pg_url.replace("postgresql://", "postgresql+asyncpg://")
    os.environ["DATABASE_URL"] = asyncpg_url

    # Redis URLs (broker + backend)
    redis_host = redis.get_container_host_ip()
    redis_port = redis.get_exposed_port(6379)
    os.environ["CELERY_BROKER_URL"] = f"redis://{redis_host}:{redis_port}/0"
    os.environ["CELERY_RESULT_BACKEND"] = f"redis://{redis_host}:{redis_port}/1"

    # Use a fixed test secret key
    os.environ["SECRET_KEY"] = "test-secret-key-for-ci"

    # (Optional) Force Celery to run tasks synchronously in tests
    os.environ["CELERY_TASK_ALWAYS_EAGER"] = "True"

    yield
    # Cleanup is handled automatically when the containers stop
