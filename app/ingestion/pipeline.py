from __future__ import annotations

import logging
import os
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from uuid import uuid4

from .config import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_MANIFEST_PATH,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_DELAY_S,
    EXTENSION_DESCRIPTION,
    FileLock,
    IngestionConfig,
    SUPPORTED_EXTENSIONS,
)
from .models import (
    FileRecord,
    FileResult,
    PipelineReport,
    ScanDiff,
)
from .parsers import parse, list_available
from .scanner import Manifest, Scanner

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lazy-loaded langchain-dependent helpers
# ---------------------------------------------------------------------------

def _make_splitter(config: IngestionConfig):
    """Create a document splitter based on the configured strategy."""
    if config.chunk_strategy == "semantic":
        from .semantic_chunker import SemanticChunker
        return SemanticChunker(
            max_chars=config.chunk_size,
            overlap_chars=config.chunk_overlap,
        )
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    return RecursiveCharacterTextSplitter(
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap,
    )


# ---------------------------------------------------------------------------
# Pipeline orchestrator
# ---------------------------------------------------------------------------

class IngestionPipeline:
    """
    Production-grade file ingestion pipeline.

    Stages:
      1. Scan       — walk directory tree, compute SHA256 hashes
      2. Diff       — compare against manifest → new / modified / deleted / unchanged
      3. Pre-clean  — delete chunks for removed files from vector store + Whoosh
      4. Parse      — extract text from each file type
      5. Chunk      — RecursiveCharacterTextSplitter
      6. Embed      — generate embeddings, store in pgvector
      7. Index      — incremental Whoosh BM25 update
      8. Save       — persist updated manifest

    Design principles:
      - Idempotent: re-running with no changes is a no-op.
      - Incremental: only touched files consume resources.
      - Error isolation: a single file failure never halts the batch.
      - Retry with back-off for transient storage failures.
      - Structured logging throughout.
      - File-based lock prevents concurrent runs.
    """

    def __init__(self, config: IngestionConfig):
        self._config = config
        self._scanner = Scanner(config)
        self._manifest = Manifest(config)
        self._splitter = None  # lazy-init

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> PipelineReport:
        """Execute one full ingestion cycle. Returns a detailed report."""
        pipeline_id = str(uuid4())[:8]
        started_at = datetime.utcnow()
        report = PipelineReport(
            pipeline_id=pipeline_id,
            started_at=started_at,
            config_source=str(self._config.resolve_source_dir()),
        )

        log_prefix = "[ingest:{}]".format(pipeline_id)
        logger.info("%s Pipeline started — source=%s", log_prefix, report.config_source)

        # --- 1. Scan ----------------------------------------------------
        logger.info("%s Stage 1/8: Scanning files…", log_prefix)
        t0 = time.monotonic()
        try:
            current = self._scanner.scan()
        except Exception as exc:
            logger.error("%s Scan failed: %s", log_prefix, exc)
            report.duration_ms = round((time.monotonic() - t0) * 1000, 2)
            return report
        report.scanned = len(current)
        logger.info("%s Found %d files", log_prefix, report.scanned)

        # --- 2. Diff ----------------------------------------------------
        logger.info("%s Stage 2/8: Computing diff against manifest…", log_prefix)
        self._manifest.load()
        diff = self._manifest.diff(current)
        report.processed = len(diff.to_process)
        report.deleted = len(diff.deleted)

        if not diff.to_process and not diff.deleted:
            logger.info("%s Nothing to do — all files unchanged", log_prefix)
            report.duration_ms = round((time.monotonic() - t0) * 1000, 2)
            return report

        # --- 3. Pre-clean (deleted files) -------------------------------
        if diff.deleted:
            logger.info("%s Stage 3/8: Cleaning %d deleted files from store…",
                        log_prefix, len(diff.deleted))
            self._delete_from_store([d.rel_path for d in diff.deleted])

        # --- 4–7. Process each changed file -----------------------------
        files_to_process = diff.to_process
        logger.info("%s Stage 4–7: Processing %d files (%d new, %d modified)…",
                     log_prefix, len(files_to_process), len(diff.new), len(diff.modified))

        for i, file_record in enumerate(files_to_process):
            rel_path = file_record.rel_path
            logger.info("%s   [%d/%d] %s", log_prefix, i + 1, len(files_to_process), rel_path)

            result = self._process_file(file_record)
            report.file_results.append(result)
            if result.status == "success":
                report.succeeded += 1
                report.total_chunks += result.chunks
                file_record.last_ingested = datetime.utcnow()
            elif result.status == "failed":
                report.failed += 1

        # --- 8. Save manifest -------------------------------------------
        logger.info("%s Stage 8/8: Saving manifest…", log_prefix)
        try:
            self._manifest.save(current)
        except Exception as exc:
            logger.error("%s Failed to save manifest: %s", log_prefix, exc)

        report.duration_ms = round((time.monotonic() - t0) * 1000, 2)
        logger.info(
            "%s Pipeline complete — %d succeeded, %d failed, %d deleted, %d chunks in %.2fs",
            log_prefix, report.succeeded, report.failed, report.deleted,
            report.total_chunks, report.duration_ms / 1000,
        )
        return report

    def run_with_lock(self) -> Optional[PipelineReport]:
        lock_path = self._config.resolve_source_dir().parent / ".ingest.lock"
        try:
            with FileLock(lock_path):
                return self.run()
        except RuntimeError:
            logger.warning("Pipeline already running (lock held) — skipping")
            return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _process_file(self, record: FileRecord) -> FileResult:
        root = self._config.resolve_source_dir()
        abs_path = root / record.rel_path
        t0 = time.monotonic()

        if not abs_path.is_file():
            return FileResult(
                rel_path=record.rel_path,
                status="skipped",
                error="File vanished before processing",
                duration_ms=0.0,
            )

        try:
            raw_docs = self._parse_with_retry(abs_path)
            if not raw_docs:
                return FileResult(
                    rel_path=record.rel_path,
                    status="failed",
                    error="Parser returned no content",
                    duration_ms=round((time.monotonic() - t0) * 1000, 2),
                )

            chunks = self._split_and_tag(raw_docs, record.rel_path)
            self._store_with_retry(chunks)
            self._index_with_retry(chunks)

            return FileResult(
                rel_path=record.rel_path,
                status="success",
                chunks=len(chunks),
                duration_ms=round((time.monotonic() - t0) * 1000, 2),
            )
        except Exception as exc:
            logger.error("Failed to process %s: %s", record.rel_path, exc)
            return FileResult(
                rel_path=record.rel_path,
                status="failed",
                error=str(exc)[:200],
                duration_ms=round((time.monotonic() - t0) * 1000, 2),
            )

    def _parse_with_retry(self, path: Path) -> list:
        from .parsers import parse
        for attempt in range(1, self._config.max_retries + 1):
            try:
                return parse(path)
            except Exception as exc:
                logger.warning("Parse attempt %d/%d failed for %s: %s",
                               attempt, self._config.max_retries, path.name, exc)
                if attempt < self._config.max_retries:
                    time.sleep(self._config.retry_delay_s)
                else:
                    raise

    def _split_and_tag(self, docs: list, rel_path: str, project_id: Optional[str] = None, owner_id: Optional[str] = None) -> list:
        if self._splitter is None:
            self._splitter = _make_splitter(self._config)
        chunks = self._splitter.split_documents(docs)
        for chunk in chunks:
            chunk.metadata["filename"] = Path(rel_path).name
            chunk.metadata["chunk_id"] = str(uuid4())
            chunk.metadata["file_type"] = Path(rel_path).suffix.lower()
            chunk.metadata["ingestion_path"] = rel_path
            chunk.metadata["collection_name"] = "own_gpt_docs"
            pid = project_id or getattr(self._config, "project_id", None)
            oid = owner_id or getattr(self._config, "owner_id", None)
            if pid:
                chunk.metadata["project_id"] = pid
            if oid:
                chunk.metadata["owner_id"] = oid
        return chunks

    def _store_with_retry(self, chunks: list) -> None:
        for attempt in range(1, self._config.max_retries + 1):
            try:
                from app.services.vector_store import add_documents_to_store
                ids = [c.metadata["chunk_id"] for c in chunks]
                add_documents_to_store(chunks, ids=ids)
                return
            except Exception as exc:
                logger.warning("Store attempt %d/%d failed: %s",
                               attempt, self._config.max_retries, exc)
                if attempt < self._config.max_retries:
                    time.sleep(self._config.retry_delay_s)
                else:
                    raise

    def _index_with_retry(self, chunks: list) -> None:
        try:
            from app.core.whoosh_manager import add_to_whoosh_index
            add_to_whoosh_index(chunks)
        except Exception as exc:
            logger.warning("Whoosh index update failed (non-fatal): %s", exc)

    def _delete_from_store(self, rel_paths: list) -> None:
        filenames = {Path(p).name for p in rel_paths}
        for fn in filenames:
            try:
                from app.services.vector_store import vector_store
                store = vector_store()
                store.delete(filter={"filename": fn})
                logger.info("Deleted chunks for '%s' from pgvector", fn)

                from app.core.whoosh_manager import delete_from_whoosh_index
                delete_from_whoosh_index(source=fn)
                logger.info("Deleted '%s' from Whoosh index", fn)
            except Exception as exc:
                logger.warning("Failed to delete '%s' from store: %s", fn, exc)
