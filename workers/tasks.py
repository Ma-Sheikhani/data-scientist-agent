import os
import socket
import time

import pandas as pd
from celery.utils.log import get_task_logger
from prometheus_client import CollectorRegistry, Counter, Histogram, push_to_gateway
from sqlalchemy import select

from agent.data_utils import build_dataframe_info, validate_csv
from agent.graph import agent_app
from agent.state import AgentState
from api.core.sync_database import SessionLocal
from api.models.job import Job, JobStatus
from api.services.file_service import _get_upload_dir
from workers.celery_app import celery_app

logger = get_task_logger(__name__)

AGENT_TIMEOUT = int(os.getenv("AGENT_TIMEOUT", "300"))

# Worker‑local Prometheus registry and metrics
worker_registry = CollectorRegistry()

JOB_COMPLETED = Counter(
    "jobs_completed_total",
    "Total number of successfully completed analysis jobs",
    registry=worker_registry,
)
JOB_FAILED = Counter(
    "jobs_failed_total",
    "Total number of failed analysis jobs",
    registry=worker_registry,
)
JOB_DURATION = Histogram(
    "job_duration_seconds",
    "Processing time per job",
    buckets=[1, 5, 10, 30, 60, 120, 300],
    registry=worker_registry,
)

PUSHGATEWAY_URL = os.getenv("PUSHGATEWAY_URL", "http://pushgateway:9091")


# ---------------------------------------------------------------------------
#  Synchronous agent runner (blocking, run in thread pool)
# ---------------------------------------------------------------------------
def run_agent_with_timeout(state: AgentState, timeout: int) -> dict:
    """Run the LangGraph agent in a thread with a timeout."""
    import threading

    result_holder: dict = {}
    exception_holder: Exception | None = None

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
#  Async analysis logic
# ---------------------------------------------------------------------------
def perform_analysis(job_id: str) -> None:
    """Synchronous analysis: read CSV, run agent, update database."""
    session = SessionLocal()

    # Retrieve the job first – always defined, early return if missing
    job = session.execute(select(Job).where(Job.id == job_id)).scalar_one_or_none()
    if not job:
        logger.error(f"Job {job_id} not found")
        session.close()
        return

    result = None
    try:
        job.status = JobStatus.RUNNING
        session.commit()

        file_path = _get_upload_dir() / job.input_file_path

        # 1. Read and validate CSV
        df = pd.read_csv(file_path)
        validate_csv(df)
        df_info = build_dataframe_info(df)

        # 2. Create agent state
        state = AgentState(
            user_question=job.question,
            dataframe_info=df_info,
            file_path=str(file_path),
        )

        # 3. Run agent (synchronous, uses a thread internally for timeout)
        result = run_agent_with_timeout(state, AGENT_TIMEOUT)

        if "error" in result:
            job.status = JobStatus.FAILED
            job.result = {"error": result["error"]}
            session.commit()
            return

        final_answer = result.get("final_answer")
        if final_answer is None:
            job.status = JobStatus.FAILED
            job.result = {"error": "Agent finished without final_answer"}
            session.commit()
            return

        # 4. Collect images (limit 10)
        all_images: list[str] = []
        for step in result.get("execution_results", []):
            for img in step.get("images", []):
                if len(all_images) >= 10:
                    break
                all_images.append(img)
            if len(all_images) >= 10:
                break

        # 5. Store success
        job.result = {
            "summary": final_answer.get("summary", ""),
            "statistics": final_answer.get("statistics", {}),
            "figures": final_answer.get("figures", []),
            "tables": final_answer.get("tables", []),
            "images": all_images,
        }
        job.status = JobStatus.COMPLETED
        session.commit()
        logger.info(f"Job {job_id} completed successfully")

    except FileNotFoundError:
        job.status = JobStatus.FAILED
        job.result = {"error": "Uploaded file missing"}
        session.commit()
    except pd.errors.ParserError:
        job.status = JobStatus.FAILED
        job.result = {"error": "Invalid CSV format"}
        session.commit()
    except Exception as e:
        logger.exception(f"Job {job_id} failed")
        job.status = JobStatus.FAILED
        error_result = {"error": str(e)}
        if (
            result is not None
            and isinstance(result, dict)
            and "execution_results" in result
        ):
            error_result["execution_trace"] = result["execution_results"]
        job.result = error_result
        session.commit()
    finally:
        session.close()


# ---------------------------------------------------------------------------
#  Celery task – only retries on true infrastructure failures
# ---------------------------------------------------------------------------
@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def process_analysis(self, job_id: str):
    start_time = time.time()
    success = False

    try:
        perform_analysis(job_id)
        success = True
    except Exception as e:
        logger.error(f"Infrastructure failure: {e}")
        success = False
        raise self.retry(exc=e)
    finally:
        duration = time.time() - start_time
        is_final = success or (self.request.retries >= self.max_retries)

        if is_final:
            if success:
                JOB_COMPLETED.inc()
            else:
                JOB_FAILED.inc()
            JOB_DURATION.observe(duration)

            push_to_gateway(
                PUSHGATEWAY_URL,
                job="celery_worker",
                grouping_key={"instance": socket.gethostname()},
                registry=worker_registry,
            )
