"""Endpoints for analysis job submission and status."""

import base64
import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from workers.tasks import process_analysis

from ..core.database import get_db
from ..dependencies import get_current_user
from ..models.job import Job, JobStatus
from ..models.user import User
from ..schemas.job import JobStatusResponse
from ..services.file_service import save_upload_file

SANDBOX_URL = os.getenv("SANDBOX_URL", "http://sandbox:8001")

router = APIRouter(prefix="/v1", tags=["analysis"])


@router.post("/analyze", response_model=JobStatusResponse, status_code=201)
async def submit_analysis(
    file: UploadFile = File(...),
    question: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit a CSV file and question for analysis."""
    # Ensure filename exists
    if not file.filename:
        raise HTTPException(status_code=400, detail="File name is missing")

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
    process_analysis.delay(str(job.id))

    return job


@router.get("/analyze/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the current status of an analysis job."""
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/analyze/{job_id}/figure/{index}")
async def get_figure(
    job_id: uuid.UUID,
    index: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    )
    job = result.scalar_one_or_none()
    if not job or not job.result:
        raise HTTPException(status_code=404, detail="Job or figure not found")

    images = job.result.get("images", [])
    if index < 0 or index >= len(images):
        raise HTTPException(status_code=404, detail="Figure index out of range")

    img_bytes = base64.b64decode(images[index])
    return Response(content=img_bytes, media_type="image/png")


@router.get("/agent-health")
async def agent_health():
    import httpx

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{SANDBOX_URL}/docs")  # just a ping
        sandbox_ok = resp.status_code == 200
    except Exception:
        sandbox_ok = False
    return {"sandbox": sandbox_ok}
