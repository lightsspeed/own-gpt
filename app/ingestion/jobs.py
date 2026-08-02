"""arq worker: processes queued ingestion jobs.

Run with: arq app.ingestion.jobs.WorkerSettings
"""

import logging
import time

from arq.connections import RedisSettings
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.ingestion.processor import delete_chunks, process_file
from app.models.ingestion import IngestionJob

logger = logging.getLogger(__name__)


async def process_ingestion_job(ctx, job_id: str) -> dict:
    start = time.monotonic()

    async with AsyncSessionLocal() as db:
        job = (
            await db.execute(select(IngestionJob).where(IngestionJob.id == job_id))
        ).scalar_one_or_none()
        if job is None:
            logger.warning("ingestion_job_missing job_id=%s", job_id)
            return {"status": "missing"}
        job.status = "processing"
        job.error = ""
        await db.commit()

    # Retries may have left partial chunks from a failed attempt.
    if ctx.get("job_try", 1) > 1:
        await delete_chunks(job.filename)

    try:
        result = await process_file(job.filename)
    except Exception as exc:
        logger.exception("ingestion_job_failed job_id=%s filename=%s", job_id, job.filename)
        async with AsyncSessionLocal() as db:
            job = (
                await db.execute(select(IngestionJob).where(IngestionJob.id == job_id))
            ).scalar_one()
            job.status = "failed"
            job.error = str(exc)[:1000]
            job.latency_ms = int((time.monotonic() - start) * 1000)
            await db.commit()
        raise

    status = "duplicate" if result.get("duplicate") else "completed"
    async with AsyncSessionLocal() as db:
        job = (
            await db.execute(select(IngestionJob).where(IngestionJob.id == job_id))
        ).scalar_one()
        job.status = status
        job.chunks = result["chunks"]
        job.sha256 = result["sha256"]
        job.latency_ms = int((time.monotonic() - start) * 1000)
        await db.commit()

    logger.info("ingestion_job_done job_id=%s status=%s chunks=%d", job_id, status, result["chunks"])
    return {"status": status, "chunks": result["chunks"]}


process_ingestion_job.max_tries = 3
process_ingestion_job.backoff = 3


class WorkerSettings:
    functions = [process_ingestion_job]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    max_jobs = 1
    job_timeout = 3600
    keep_result = 3600
