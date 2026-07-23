"""Endpoints for analysis job submission and status."""

import base64
import logging
import os
import re
import uuid
from pathlib import Path

import magic
import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.limiter import limiter
from api.core.metrics import ANALYSIS_REQUESTS
from api.services.pii_service import redact_pii_from_csv
from workers.tasks import process_analysis

from ..core.database import get_db
from ..dependencies import get_current_user
from ..models.job import Job, JobStatus
from ..models.user import User
from ..schemas.job import JobStatusResponse
from ..services.file_service import save_upload_file

logger = logging.getLogger(__name__)

SANDBOX_URL = os.getenv("SANDBOX_URL", "http://sandbox:8001")

router = APIRouter(prefix="/v1", tags=["analysis"])

ALLOWED_MIMES = {
    "text/csv",
    "text/plain",
    "application/csv",
    "application/vnd.ms-excel",
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("/analyze", response_model=JobStatusResponse, status_code=201)
@limiter.limit("5/minute")
async def submit_analysis(
    request: Request,
    file: UploadFile = File(...),
    question: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit a CSV file and question for analysis."""
    # Ensure filename exists
    if not file.filename:
        raise HTTPException(status_code=400, detail="File name is missing")

    # 1. File size check
    if file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large. Maximum 10 MB.")

    # 2. Sanitize filename
    original_filename = Path(file.filename).name
    if not original_filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files allowed")

    # Read file content (we'll reuse it)
    content = await file.read()

    # 3. MIME type check (using already read content)
    detected_mime = magic.from_buffer(content, mime=True)
    if detected_mime not in ALLOWED_MIMES:
        raise HTTPException(
            status_code=400, detail=f"Unsupported file type: {detected_mime}"
        )

    # 4. Question field: prevent injection (simple regex)
    if re.search(r"[;`]|\b(exec|eval|import)\b", question):
        raise HTTPException(status_code=400, detail="Invalid characters in question")

    # Save file using the sanitized name
    file_path = save_upload_file(content, original_filename)

    # PII redaction (optional, enabled by default)
    if os.getenv("ENABLE_PII_REDACTION", "true").lower() == "true":
        try:
            df = pd.read_csv(file_path)
            df = redact_pii_from_csv(df)
            df.to_csv(file_path, index=False)
            logger.info("PII redaction applied to uploaded CSV")
        except Exception as e:
            logger.warning(f"PII redaction failed: {e}")

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

    # Increment metric
    ANALYSIS_REQUESTS.labels(status="submitted").inc()
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
