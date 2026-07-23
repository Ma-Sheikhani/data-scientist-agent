"""FastAPI application entry point."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from alembic import command
from alembic.config import Config
from api.core.config import settings
from api.core.database import Base, engine
from api.core.limiter import limiter

from .routers import analysis, auth

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Automatically migrate the database on startup."""
    try:
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrated to latest version.")
    except Exception as e:
        logger.warning(f"Alembic migration failed ({e}). Creating tables from models.")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Tables created via create_all.")
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.3.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    lambda request, exc: _rate_limit_exceeded_handler(request, exc),
)


instrumentator = Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
    should_instrument_requests_inprogress=True,
    excluded_handlers=["/health", "/metrics"],  # avoid double-counting
    inprogress_name="http_requests_inprogress",
    inprogress_labels=True,
)

instrumentator.instrument(app).expose(app, endpoint="/metrics", include_in_schema=True)

app.include_router(auth.router)
app.include_router(analysis.router)


# CORS (allow all origins for dev, restrict later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


if os.getenv("ENABLE_TEST_ENDPOINTS", "false").lower() == "true":
    from fastapi import HTTPException

    @app.get("/test-trigger-500")
    async def test_trigger_500():
        raise HTTPException(
            status_code=500, detail="Test error triggered for monitoring alert"
        )
