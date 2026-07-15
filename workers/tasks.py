import asyncio
from typing import Optional

import pandas as pd
from celery.utils.log import get_task_logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import async_session_maker
from api.models.job import Job, JobStatus
from api.services.file_service import _get_upload_dir
from workers.celery_app import celery_app

logger = get_task_logger(__name__)


# ---------------------------------------------------------------------------
#  Async core – now accepts an optional session for testing
# ---------------------------------------------------------------------------
async def _run_analysis(job_id: str, session: Optional[AsyncSession] = None) -> None:
    logger.info(f"Picked up job {job_id}")

    if session is None:
        # Normal operation – create a new session
        async with async_session_maker() as session:
            await _run_analysis_with_session(job_id, session)
    else:
        # Test mode – use the provided session directly
        await _run_analysis_with_session(job_id, session)


async def _run_analysis_with_session(job_id: str, session: AsyncSession) -> None:
    """The actual analysis logic, operating on the given session."""
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        logger.error(f"Job {job_id} not found")
        return

    # Mark as running
    job.status = JobStatus.RUNNING
    await session.commit()

    try:
        file_path = _get_upload_dir() / job.input_file_path
        df = pd.read_csv(file_path)
        shape = df.shape

        # Simulate work
        await asyncio.sleep(2)

        job.result = {
            "shape": shape,
            "columns": df.columns.tolist(),
            "message": "Dummy analysis completed",
        }
        job.status = JobStatus.COMPLETED
        await session.commit()

    except FileNotFoundError:
        job.status = JobStatus.FAILED
        job.result = {"error": "Uploaded file missing"}
        await session.commit()
    except pd.errors.ParserError:
        job.status = JobStatus.FAILED
        job.result = {"error": "Invalid CSV format"}
        await session.commit()
    except Exception as e:
        job.status = JobStatus.FAILED
        job.result = {"error": str(e)}
        await session.commit()
        raise  # let the caller (Celery or test) handle retries


# ---------------------------------------------------------------------------
#  Celery task – used in production / normal operation
# ---------------------------------------------------------------------------
@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def process_analysis(self, job_id: str):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(_run_analysis(job_id))
    except Exception as e:
        raise self.retry(exc=e)
