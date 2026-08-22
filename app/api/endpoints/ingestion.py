"""Ingestion API: queue uploads for async processing and expose job status."""

import hashlib
import logging
import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import api_error, get_current_user
from app.core.config import settings
from app.core.database import AsyncSessionLocal, get_db, get_sync_db
from app.ingestion.processor import MAX_FILE_BYTES, SUPPORTED_TYPES, UPLOAD_DIR
from app.models.ingestion import IngestedFile, IngestionJob
from app.models.user import User
from app.services.memory import resolve_owned_project

logger = logging.getLogger(__name__)
router = APIRouter()


async def _get_pool():
    from arq.connections import RedisSettings, create_pool
    return await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))


class UploadResponse(BaseModel):
    filename: str
    # queued | duplicate | error
    status: str
    job_id: Optional[str] = None
    chunks: int = 0
    message: str
    file_type: str


class JobResponse(BaseModel):
    id: str
    filename: str
    status: str
    sha256: str
    chunks: int
    error: str
    latency_ms: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


def _job_to_dict(job: IngestionJob) -> dict:
    return {
        "id": str(job.id),
        "filename": job.filename,
        "status": job.status,
        "sha256": job.sha256,
        "chunks": job.chunks,
        "error": job.error,
        "latency_ms": job.latency_ms,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


async def _enqueue(job: IngestionJob) -> None:
    pool = await _get_pool()
    try:
        await pool.enqueue_job("process_ingestion_job", str(job.id))
    finally:
        await pool.aclose()


def _require_owned_project(db: Session, project_id: Optional[str], user: User) -> None:
    """Verify the project exists and belongs to the requesting user (404 otherwise)."""
    if not project_id:
        return
    try:
        resolve_owned_project(db, project_id, user.id)
    except ValueError:
        raise api_error(404, "project_not_found", "Project not found")


@router.post("/documents/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    project_id: Optional[str] = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db),
):
    _require_owned_project(db, project_id, user)
    ext = os.path.splitext(file.filename)[-1].lower()
    if ext not in SUPPORTED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Supported: {', '.join(SUPPORTED_TYPES)}",
        )

    content = await file.read()
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {MAX_FILE_BYTES // (1024 * 1024)} MB limit",
        )

    dest = UPLOAD_DIR / file.filename
    with open(dest, "wb") as f:
        f.write(content)
    sha256 = hashlib.sha256(content).hexdigest()

    async with AsyncSessionLocal() as db:
        existing = (
            await db.execute(select(IngestedFile).where(IngestedFile.filename == file.filename))
        ).scalar_one_or_none()
        if existing is not None:
            if existing.sha256 == sha256:
                return UploadResponse(
                    filename=file.filename,
                    status="duplicate",
                    chunks=existing.chunks,
                    message=f"'{file.filename}' is already ingested ({existing.chunks} chunks).",
                    file_type=ext,
                )
            else:
                from app.ingestion.processor import purge_document_lifecycle
                await purge_document_lifecycle(file.filename)

        job = IngestionJob(filename=file.filename, sha256=sha256, status="pending", project_id=project_id)
        db.add(job)
        await db.commit()
        await db.refresh(job)

    await _enqueue(job)
    return UploadResponse(
        filename=file.filename,
        status="queued",
        job_id=str(job.id),
        chunks=0,
        message=f"Queued ingestion for '{file.filename}'.",
        file_type=ext,
    )


@router.post("/documents/upload/batch", response_model=list[UploadResponse])
async def upload_documents(
    files: list[UploadFile] = File(...),
    project_id: Optional[str] = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_sync_db),
):
    _require_owned_project(db, project_id, user)
    results = []
    for f in files:
        filename = f.filename or "unknown"
        try:
            results.append(await upload_document(f, project_id=project_id, user=user, db=db))
        except HTTPException as exc:
            results.append(UploadResponse(
                filename=filename,
                status="error",
                chunks=0,
                message=exc.detail,
                file_type="",
            ))
    return results


@router.get("/ingestion/jobs", response_model=list[JobResponse])
async def list_ingestion_jobs(limit: int = 50, db=Depends(get_db)):
    result = await db.execute(
        select(IngestionJob)
        .order_by(IngestionJob.created_at.desc())
        .limit(min(limit, 200))
    )
    return [_job_to_dict(job) for job in result.scalars()]


@router.get("/ingestion/jobs/{job_id}", response_model=JobResponse)
async def get_ingestion_job(job_id: str, db=Depends(get_db)):
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Job not found")
    job = (
        await db.execute(select(IngestionJob).where(IngestionJob.id == job_uuid))
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_to_dict(job)
