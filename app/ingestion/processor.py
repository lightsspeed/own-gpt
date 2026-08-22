"""Unified document ingestion pipeline.

parse -> chunk -> embed (batched, with retry/backoff) -> pgvector + whoosh.

Shared by the queued HTTP upload path (arq worker) and the batch script.
"""

import hashlib
import logging
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Optional

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy import select, text

from app.core.database import AsyncSessionLocal
from app.core.whoosh_manager import add_to_whoosh_index, delete_from_whoosh_index
from app.models.ingestion import IngestedFile
from app.services.vector_store import embeddings, vector_store

logger = logging.getLogger(__name__)

SUPPORTED_TYPES = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
}

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
EMBED_BATCH_SIZE = 100
EMBED_MAX_RETRIES = 4
EMBED_BACKOFF = 1.5
MAX_FILE_BYTES = 100 * 1024 * 1024


def compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(64 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_documents(filename: str, ext: str) -> list[Document]:
    file_path = UPLOAD_DIR / filename
    if ext == ".pdf":
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(file_path.read_bytes())
            tmp_path = tmp.name
        try:
            docs = PyPDFLoader(tmp_path).load()
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    else:
        text_content = file_path.read_text(encoding="utf-8", errors="replace")
        docs = [Document(page_content=text_content, metadata={"source": filename, "file_type": ext})]
    for doc in docs:
        if doc.page_content:
            doc.page_content = doc.page_content.replace("\x00", "")
    return docs


def _embed_batch(texts: list[str]) -> list[list[float]]:
    last_error: Exception | None = None
    for attempt in range(1, EMBED_MAX_RETRIES + 1):
        try:
            return embeddings.embed_documents(texts)
        except Exception as exc:
            last_error = exc
            wait = EMBED_BACKOFF * (2 ** (attempt - 1))
            logger.warning(
                "embedding_retry attempt=%d/%d wait=%.1fs error=%s",
                attempt, EMBED_MAX_RETRIES, wait, exc,
            )
            time.sleep(wait)
    raise RuntimeError(f"Embedding failed after {EMBED_MAX_RETRIES} attempts: {last_error}")


async def purge_document_lifecycle(filename: str, project_id: Optional[str] = None) -> dict:
    """Purge all document records and index entries across the entire platform lifecycle.

    Synchronizes deletion across:
    1. PGVector chunks (langchain_pg_embedding table)
    2. Whoosh BM25 index (delete_from_whoosh_index)
    3. IngestedFile DB model (ingested_files table)
    4. IngestionJob DB models (ingestion_jobs table)
    5. Physical upload file on disk (data/uploads/<filename>)

    Resilient to partial failures and safe for idempotent retries.
    """
    from sqlalchemy import delete
    from app.models.ingestion import IngestionJob

    stats = {
        "filename": filename,
        "pgvector_deleted": 0,
        "whoosh_deleted": 0,
        "ingested_file_deleted": False,
        "ingestion_jobs_deleted": 0,
        "file_unlinked": False,
    }

    # 1. Clean PGVector chunks, IngestedFile DB record, and IngestionJob records
    async with AsyncSessionLocal() as db:
        if project_id:
            res_pg = await db.execute(
                text(
                    "DELETE FROM langchain_pg_embedding "
                    "WHERE (cmetadata->>'filename' = :name OR cmetadata->>'source' = :name2) "
                    "AND cmetadata->>'project_id' = :pid"
                ),
                {"name": filename, "name2": filename, "pid": project_id},
            )
        else:
            res_pg = await db.execute(
                text(
                    "DELETE FROM langchain_pg_embedding "
                    "WHERE cmetadata->>'filename' = :name OR cmetadata->>'source' = :name2"
                ),
                {"name": filename, "name2": filename},
            )
        stats["pgvector_deleted"] = res_pg.rowcount or 0

        # Delete from ingested_files table
        res_file = await db.execute(
            delete(IngestedFile).where(IngestedFile.filename == filename)
        )
        stats["ingested_file_deleted"] = (res_file.rowcount or 0) > 0

        # Delete from ingestion_jobs table
        res_job = await db.execute(
            delete(IngestionJob).where(IngestionJob.filename == filename)
        )
        stats["ingestion_jobs_deleted"] = res_job.rowcount or 0

        await db.commit()

    # 2. Clean Whoosh BM25 index
    try:
        whoosh_count = delete_from_whoosh_index(filename)
        stats["whoosh_deleted"] = whoosh_count
    except Exception as exc:
        logger.warning("whoosh_delete_failed filename=%s error=%s", filename, exc)

    # 3. Clean physical upload file from disk
    file_path = UPLOAD_DIR / filename
    if file_path.exists():
        try:
            file_path.unlink()
            stats["file_unlinked"] = True
        except Exception as exc:
            logger.warning("file_unlink_failed filename=%s error=%s", filename, exc)

    logger.info("purge_document_lifecycle_completed stats=%s", stats)
    return stats


async def delete_chunks(filename: str) -> None:
    """Backwards-compatible wrapper that purges all traces of a document lifecycle."""
    await purge_document_lifecycle(filename)


async def _upsert_ingested(filename: str, sha256: str, chunks: int) -> None:
    async with AsyncSessionLocal() as db:
        row = (
            await db.execute(select(IngestedFile).where(IngestedFile.filename == filename))
        ).scalar_one_or_none()
        if row is None:
            db.add(IngestedFile(filename=filename, sha256=sha256, chunks=chunks))
        else:
            row.sha256 = sha256
            row.chunks = chunks
        await db.commit()


async def process_file(
    filename: str,
    force: bool = False,
    project_id: Optional[str] = None,
    owner_id: Optional[str] = None,
) -> dict:
    """Ingest one file into pgvector + whoosh.

    Returns {"chunks": int, "sha256": str, "duplicate": bool}.
    Raises on unsupported type, missing file, size overflow, or embedding failure.
    """
    ext = os.path.splitext(filename)[-1].lower()
    if ext not in SUPPORTED_TYPES:
        raise ValueError(f"Unsupported file type '{ext}'. Supported: {', '.join(SUPPORTED_TYPES)}")

    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        raise FileNotFoundError(f"Uploaded file missing: {filename}")
    if file_path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError(f"File exceeds {MAX_FILE_BYTES // (1024 * 1024)} MB limit")

    sha256 = compute_sha256(file_path)

    async with AsyncSessionLocal() as db:
        existing = (
            await db.execute(select(IngestedFile).where(IngestedFile.filename == filename))
        ).scalar_one_or_none()
    if existing is not None and existing.sha256 == sha256 and not force:
        logger.info("ingestion_duplicate filename=%s chunks=%d", filename, existing.chunks)
        return {"chunks": existing.chunks, "sha256": sha256, "duplicate": True}
    if existing is not None:
        logger.info("ingestion_changed_reembed filename=%s", filename)
        await purge_document_lifecycle(filename, project_id=project_id)

    docs = _load_documents(filename, ext)
    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    splits = splitter.split_documents(docs)

    for idx, chunk in enumerate(splits):
        chunk.metadata["filename"] = filename
        chunk.metadata["chunk_id"] = str(uuid.uuid4())
        chunk.metadata["chunk_index"] = idx
        if project_id:
            chunk.metadata["project_id"] = project_id
        if owner_id:
            chunk.metadata["owner_id"] = owner_id

    texts = [c.page_content for c in splits]
    ids = [c.metadata["chunk_id"] for c in splits]
    metadatas = [c.metadata for c in splits]

    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        end = start + EMBED_BATCH_SIZE
        batch_embeddings = _embed_batch(texts[start:end])
        vector_store.add_embeddings(
            texts=texts[start:end],
            embeddings=batch_embeddings,
            metadatas=metadatas[start:end],
            ids=ids[start:end],
        )
        logger.info("ingestion_embed_batch filename=%s offset=%d/%d", filename, end, len(texts))

    try:
        add_to_whoosh_index(splits)
    except Exception as exc:
        logger.warning("whoosh_update_failed error=%s", exc)

    await _upsert_ingested(filename, sha256, len(splits))
    logger.info("ingestion_complete filename=%s chunks=%d sha256=%s", filename, len(splits), sha256)
    return {"chunks": len(splits), "sha256": sha256, "duplicate": False}
