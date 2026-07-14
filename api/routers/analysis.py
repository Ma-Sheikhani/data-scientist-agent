import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..dependencies import get_current_user
from ..models.job import Job, JobStatus
from ..models.user import User
from ..schemas.job import JobStatusResponse
from ..services.file_service import save_upload_file

router = APIRouter(prefix="/v1", tags=["analysis"])


@router.post("/analyze", response_model=JobStatusResponse, status_code=201)
async def submit_analysis(
    file: UploadFile = File(...),
    question: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Validate file type
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    # Save file
    content = await file.read()
    file_path = save_upload_file(content, file.filename)

    # Create job record
    job = Job(
        id=uuid.uuid4(),
        user_id=current_user.id,
        input_file_path=file_path,
        question=question,
        status=JobStatus.PENDING,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # TODO: Enqueue Celery task (Day 3)

    return job


@router.get("/analyze/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Job).where(Job.id == job_id, Job.user_id == current_user.id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
