import asyncio
import os
from typing import Optional

import pandas as pd
from celery.utils.log import get_task_logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent.data_utils import build_dataframe_info, validate_csv
from agent.graph import agent_app
from agent.state import AgentState
from api.core.database import async_session_maker
from api.models.job import Job, JobStatus
from api.services.file_service import _get_upload_dir  # we'll keep this for consistency
from workers.celery_app import celery_app

logger = get_task_logger(__name__)

AGENT_TIMEOUT = int(os.getenv("AGENT_TIMEOUT", "300"))


# ---------------------------------------------------------------------------
#  Threaded agent runner (synchronous)
# ---------------------------------------------------------------------------
def run_agent_with_timeout(state: AgentState, timeout: int) -> dict:
    """
    Run agent_app.invoke in a thread with a timeout.
    Returns the result dict.
    """
    import threading

    result_holder: dict = {}
    exception_holder = None

    def target():
        nonlocal result_holder, exception_holder
        try:
            result_holder = agent_app.invoke(state)
        except Exception as e:
            exception_holder = e

    thread = threading.Thread(target=target)
    thread.start()
    thread.join(timeout=timeout)
    if thread.is_alive():
        return {"error": f"Agent timed out after {timeout} seconds."}
    if exception_holder:
        return {"error": str(exception_holder)}
    return result_holder


# ---------------------------------------------------------------------------
#  Async core
# ---------------------------------------------------------------------------
async def _run_analysis(job_id: str, session: Optional[AsyncSession] = None) -> None:
    if session is None:
        async with async_session_maker() as session:
            await _run_analysis_with_session(job_id, session)
    else:
        await _run_analysis_with_session(job_id, session)


async def _run_analysis_with_session(job_id: str, session: AsyncSession) -> None:
    """The real analysis – now powered by the AI agent."""
    db_result = await session.execute(select(Job).where(Job.id == job_id))
    job = db_result.scalar_one_or_none()
    if not job:
        logger.error(f"Job {job_id} not found")
        return

    # Mark as running
    job.status = JobStatus.RUNNING
    await session.commit()

    result = None
    try:
        file_path = _get_upload_dir() / job.input_file_path

        # 1. Read and validate CSV
        df = pd.read_csv(file_path)
        validate_csv(df)
        df_info = build_dataframe_info(df)

        # 2. Create agent state
        state = AgentState(
            user_question=job.question,
            dataframe_info=df_info,
            file_path=str(
                file_path
            ),  # absolute path, sandbox can access it via mounted volume
        )

        # 3. Run agent with timeout
        result = run_agent_with_timeout(state, AGENT_TIMEOUT)

        if "error" in result:
            raise Exception(result["error"])

        final_answer = result.get("final_answer")
        if final_answer is None:
            raise Exception("Agent finished without final_answer")

        # 4. Collect images from all execution steps (limit to 10)
        all_images: list = []
        for step in result.get("execution_results", []):
            for img_b64 in step.get("images", []):
                if len(all_images) < 10:
                    all_images.append(img_b64)
                else:
                    break
            if len(all_images) >= 10:
                break

        # 5. Store results
        job.result = {
            "summary": final_answer.get("summary", ""),
            "statistics": final_answer.get("statistics", {}),
            "figures": final_answer.get("figures", []),
            "tables": final_answer.get("tables", []),
            "images": all_images,
        }
        job.status = JobStatus.COMPLETED
        logger.info(f"Job {job_id} completed successfully")

    except FileNotFoundError:
        job.status = JobStatus.FAILED
        job.result = {"error": "Uploaded file missing"}
    except pd.errors.ParserError:
        job.status = JobStatus.FAILED
        job.result = {"error": "Invalid CSV format"}
    except Exception as e:
        logger.exception(f"Job {job_id} failed with error: {e}")
        job.status = JobStatus.FAILED
        error_result = {"error": str(e)}

        # capture partial execution trace if available
        if result is not None and isinstance(result, dict):
            if "execution_results" in result:
                error_result["execution_trace"] = result["execution_results"]

    finally:
        await session.commit()


# ---------------------------------------------------------------------------
#  Celery task
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
