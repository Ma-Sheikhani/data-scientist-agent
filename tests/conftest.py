import asyncio
import os
import shutil
import tempfile

import nest_asyncio
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import api.routers.analysis as analysis_router  # to patch process_analysis.delay
from api.core.config import settings
from api.core.database import Base, get_db
from api.main import app
from workers.tasks import _run_analysis

# Apply nested async loop support (must happen early)
nest_asyncio.apply()

# Force Celery eager mode in tests
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "True"


# ── Test‑specific engine with NullPool ──────────────────────
test_engine = create_async_engine(
    settings.DATABASE_URL,
    poolclass=NullPool,
    echo=False,
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Session‑scoped setup / teardown ─────────────────────────
@pytest.fixture(scope="session", autouse=True)
async def setup_database():
    """Create all tables once before any test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Drop tables after all tests
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def override_upload_dir():
    """Point file uploads to a writable temp directory."""
    tmpdir = tempfile.mkdtemp()
    os.environ["UPLOAD_DIR"] = tmpdir
    yield
    shutil.rmtree(tmpdir, ignore_errors=True)


# ── Per‑test transactional session (savepoint) ──────────────
@pytest.fixture
async def db_session():
    """Session inside a savepoint – rolled back after the test."""
    async with test_engine.connect() as conn:
        await conn.begin()  # outer transaction
        async with TestSessionLocal(bind=conn) as session:
            await session.begin_nested()  # savepoint for the test
            yield session
            await session.rollback()
        await conn.rollback()


# ── Override FastAPI's database dependency for all tests ────
@pytest.fixture(autouse=True)
def override_app_db(db_session):
    async def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    yield
    app.dependency_overrides.clear()


# ── Replace Celery delay with direct call using test session ─
@pytest.fixture(autouse=True)
def mock_celery_task(db_session, monkeypatch):
    """Replace process_analysis.delay so the analysis runs
    immediately using the same transactional session."""

    async def _fake_delay(job_id):
        await _run_analysis(job_id, session=db_session)

    def _delay(job_id):
        """Synchronous wrapper that can be called by the endpoint."""
        loop = asyncio.get_event_loop()
        loop.run_until_complete(_fake_delay(job_id))

    monkeypatch.setattr(analysis_router.process_analysis, "delay", _delay)
