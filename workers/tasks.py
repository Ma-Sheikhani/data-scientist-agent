import pandas as pd
import pandas.errors
from celery.utils.log import get_task_logger
from sqlalchemy import select

from api.core.database import async_session_maker
from api.models.job import Job, JobStatus
from api.services.file_service import UPLOAD_DIR
from workers.celery_app import celery_app

logger = get_task_logger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
async def process_analysis(self, job_id: str):
    logger.info(f"Picked up job {job_id}")
    async with async_session_maker() as session:
        # 1. Fetch the job
        result = await session.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()
        if not job:
            logger.error(f"Job {job_id} not found")
            return

        # 2. Mark as running
        job.status = JobStatus.RUNNING
        await session.commit()

        try:
            # Actual processing
            file_path = UPLOAD_DIR / job.input_file_path
            df = pd.read_csv(file_path)
            shape = df.shape

            # Simulate a bit of heavy work
            import asyncio

            await asyncio.sleep(2)

            # Success → store result and commit
            job.result = {
                "shape": shape,
                "columns": df.columns.tolist(),
                "message": "Dummy analysis completed",
            }
            job.status = JobStatus.COMPLETED
            await session.commit()  # <-- only commit here for success

        except FileNotFoundError:
            # Permanent failure – file is gone, no point retrying
            job.status = JobStatus.FAILED
            job.result = {"error": "Uploaded file missing"}
            await session.commit()
            # No retry, just exit

        except pd.errors.ParserError:
            # Permanent failure – malformed CSV
            job.status = JobStatus.FAILED
            job.result = {"error": "Invalid CSV format"}
            await session.commit()

        except Exception as e:
            # Transient or unexpected – we want to retry
            job.status = JobStatus.FAILED
            job.result = {"error": str(e)}
            await session.commit()
            logger.exception(f"Job {job_id} failed, will retry")
            raise self.retry(exc=e)
