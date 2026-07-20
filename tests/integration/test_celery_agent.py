import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from sqlalchemy import delete, select

from api.core.database import async_session_maker
from api.models.job import Job, JobStatus
from api.services.file_service import UPLOAD_DIR
from workers.tasks import _run_analysis  # <-- internal function, no Celery binding


@pytest.fixture(autouse=True)
async def clean_db():
    async with async_session_maker() as session:
        async with session.begin():
            await session.execute(delete(Job))


@pytest.mark.asyncio
async def test_process_analysis_success():
    csv_content = "sepal_length,sepal_width,species\n5.1,3.5,setosa\n4.9,3.0,setosa\n"

    # Create a temporary upload directory
    with tempfile.TemporaryDirectory() as tmpdir:
        upload_dir = Path(tmpdir)
        csv_file = upload_dir / "test.csv"
        csv_file.write_text(csv_content)

        # Create a job in the database
        user_id = str(uuid.uuid4())
        async with async_session_maker() as session:
            job = Job(
                user_id=user_id,
                input_file_path="test.csv",  # just the filename
                question="correlation between sepal_length and sepal_width?",
            )
            session.add(job)
            await session.commit()
            job_id = str(job.id)

        # Mock agent, CSV reading, and the upload directory
        with (
            patch("workers.tasks.agent_app") as mock_agent,
            patch("workers.tasks.pd.read_csv") as mock_read_csv,
            patch(str(UPLOAD_DIR), upload_dir),
        ):
            mock_agent.invoke.return_value = {
                "final_answer": {
                    "summary": "The correlation is 0.87.",
                    "statistics": {"correlation": 0.87},
                    "figures": [0],
                    "tables": [],
                },
                "execution_results": [],
            }
            mock_read_csv.return_value = pd.DataFrame(
                {
                    "sepal_length": [5.1, 4.9],
                    "sepal_width": [3.5, 3.0],
                    "species": ["setosa", "setosa"],
                }
            )

            # Call the internal analysis function (no Celery)
            await _run_analysis(job_id)

        # Verify job result
        async with async_session_maker() as session:
            stmt = select(Job).where(Job.id == job_id)
            result = await session.execute(stmt)
            updated_job = result.scalar_one()
            assert updated_job.status == JobStatus.COMPLETED
            assert updated_job.result["summary"] == "The correlation is 0.87."
            assert updated_job.result["statistics"]["correlation"] == 0.87
