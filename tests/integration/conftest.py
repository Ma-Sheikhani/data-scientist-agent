import os

import pytest_asyncio
from sqlalchemy import delete

from api.core.database import async_session_maker
from api.models.job import Job
from api.models.user import User

os.environ["DATABASE_URL"] = "postgresql+asyncpg://agent:agentpass@localhost:5432/dsagent"
os.environ["CELERY_BROKER_URL"] = "redis://localhost:6379/0"
os.environ["CELERY_RESULT_BACKEND"] = "redis://localhost:6379/1"
os.environ["SECRET_KEY"] = "testsecret"
os.environ["UPLOAD_DIR"] = os.path.join(os.path.dirname(__file__), "../../test_uploads")


@pytest_asyncio.fixture(autouse=True)
async def clean_database():
    async with async_session_maker() as session:
        await session.execute(delete(Job))
        await session.execute(delete(User))
        await session.commit()
