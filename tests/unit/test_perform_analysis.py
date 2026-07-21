import unittest.mock
import uuid
from pathlib import Path

from api.core.sync_database import SessionLocal
from api.models.job import Job, JobStatus
from api.services.file_service import _get_upload_dir
from workers.tasks import perform_analysis


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _create_job_and_csv(question="?", csv_data="x,y\n1,2\n3,4\n"):
    """Create a Job + CSV file, return (job_id, file_path)."""
    upload_dir = Path(_get_upload_dir())
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_name = f"test_{uuid.uuid4().hex[:8]}.csv"
    file_path = upload_dir / file_name
    file_path.write_text(csv_data)

    session = SessionLocal()
    try:
        job = Job(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            input_file_path=file_name,
            question=question,
            status=JobStatus.PENDING,
        )
        session.add(job)
        session.commit()
        job_id = str(job.id)
    finally:
        session.close()
    return job_id, file_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_perform_analysis_success_mocked():
    """Full happy path: agent returns final_answer → job COMPLETED."""
    # Create CSV and job directly (using the same pattern as the other tests)
    job_id, file_path = _create_job_and_csv("Mock question?")

    fake_agent_result = {
        "final_answer": {
            "summary": "The correlation is 0.99.",
            "statistics": {"correlation": 0.99},
            "figures": [],
            "tables": [],
        },
        "execution_results": [{"images": []}],
    }

    with unittest.mock.patch("workers.tasks.agent_app.invoke") as mock_invoke:
        mock_invoke.return_value = fake_agent_result
        perform_analysis(job_id)

    session = SessionLocal()
    try:
        job = session.query(Job).filter(Job.id == job_id).one()
        assert job.status == JobStatus.COMPLETED
        assert job.result["summary"] == "The correlation is 0.99."
        assert job.result["statistics"] == {"correlation": 0.99}
    finally:
        session.close()

    file_path.unlink()


def test_perform_analysis_agent_error():
    """Agent returns an 'error' key → job must be marked FAILED."""
    job_id, file_path = _create_job_and_csv("error test")

    with unittest.mock.patch("workers.tasks.agent_app.invoke") as mock_invoke:
        mock_invoke.return_value = {"error": "Something went wrong"}
        perform_analysis(job_id)

    session = SessionLocal()
    try:
        job = session.query(Job).filter(Job.id == job_id).one()
        assert job.status == JobStatus.FAILED
        assert job.result["error"] == "Something went wrong"
    finally:
        session.close()

    file_path.unlink()


def test_perform_analysis_missing_final_answer():
    """Agent returns no 'final_answer' → job FAILED."""
    job_id, file_path = _create_job_and_csv("missing final answer")

    with unittest.mock.patch("workers.tasks.agent_app.invoke") as mock_invoke:
        mock_invoke.return_value = {"something": "else"}
        perform_analysis(job_id)

    session = SessionLocal()
    try:
        job = session.query(Job).filter(Job.id == job_id).one()
        assert job.status == JobStatus.FAILED
        assert "Agent finished without final_answer" in job.result["error"]
    finally:
        session.close()

    file_path.unlink()


def test_perform_analysis_csv_not_found():
    """FileNotFoundError → job FAILED with specific message."""
    job_id, file_path = _create_job_and_csv("will be deleted")
    file_path.unlink()  # remove the CSV before calling perform_analysis

    perform_analysis(job_id)

    session = SessionLocal()
    try:
        job = session.query(Job).filter(Job.id == job_id).one()
        assert job.status == JobStatus.FAILED
        assert job.result["error"] == "Uploaded file missing"
    finally:
        session.close()
