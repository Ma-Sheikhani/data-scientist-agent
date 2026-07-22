"""FastAPI application entry point."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from api.core.limiter import limiter

from .core.config import settings
from .core.database import engine
from .routers import analysis, auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables (for dev; later we'll use migrations)
    # async with engine.begin() as conn:
    #     await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
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
