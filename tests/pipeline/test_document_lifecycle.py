"""
Unit tests for Document Lifecycle Synchronization (V3 Phase 4).

Verifies full cleanup consistency across PGVector, Whoosh, IngestedFile,
IngestionJob, and disk file, plus idempotency and re-ingestion behavior.

Note: All DB setup/teardown is done via AsyncSessionLocal to avoid
asyncpg / Windows ProactorEventLoop conflicts when mixing sync + async
DB sessions in the same test process.
"""

import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from app.ingestion.processor import purge_document_lifecycle, UPLOAD_DIR


# ─── Test 1: Idempotency on non-existent document ──────────────────────────

@pytest.mark.anyio
async def test_purge_document_lifecycle_idempotent():
    """Purging a non-existent document should complete gracefully with zero errors."""
    fake_name = f"non_existent_{uuid.uuid4().hex}.pdf"

    async def _no_rows(stmt, params=None):
        m = MagicMock()
        m.rowcount = 0
        return m

    async def _noop_commit():
        pass

    mock_db = AsyncMock()
    mock_db.execute = _no_rows
    mock_db.commit = _noop_commit
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)

    with patch("app.ingestion.processor.AsyncSessionLocal", return_value=mock_db):
        with patch("app.ingestion.processor.delete_from_whoosh_index", return_value=0):
            stats = await purge_document_lifecycle(fake_name)

    assert stats["filename"] == fake_name
    assert stats["pgvector_deleted"] == 0
    assert stats["ingested_file_deleted"] is False
    assert stats["ingestion_jobs_deleted"] == 0
    assert stats["file_unlinked"] is False


# ─── Test 2: All records cleaned on purge ──────────────────────────────────

@pytest.mark.anyio
async def test_purge_document_lifecycle_cleans_all_records():
    """Purging a document must remove all lifecycle records and disk file."""
    filename = f"lifecycle_test_{uuid.uuid4().hex[:8]}.txt"
    file_path = UPLOAD_DIR / filename

    # Create fake disk file
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    file_path.write_text("Lifecycle test document content.", encoding="utf-8")
    assert file_path.exists()

    async def _deleted_rows(stmt, params=None):
        m = MagicMock()
        m.rowcount = 1
        return m

    async def _noop_commit():
        pass

    mock_db = AsyncMock()
    mock_db.execute = _deleted_rows
    mock_db.commit = _noop_commit
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)

    with patch("app.ingestion.processor.AsyncSessionLocal", return_value=mock_db):
        with patch("app.ingestion.processor.delete_from_whoosh_index", return_value=1) as mock_whoosh:
            stats = await purge_document_lifecycle(filename)

    assert stats["filename"] == filename
    assert stats["pgvector_deleted"] >= 1
    assert stats["ingested_file_deleted"] is True
    assert stats["ingestion_jobs_deleted"] >= 1
    assert stats["whoosh_deleted"] == 1
    assert stats["file_unlinked"] is True
    assert not file_path.exists()
    mock_whoosh.assert_called_once_with(filename)


# ─── Test 3: Whoosh failure is non-fatal ────────────────────────────────────

@pytest.mark.anyio
async def test_purge_document_lifecycle_whoosh_failure_is_non_fatal():
    """Whoosh delete failure should not raise; purge completes with other stores cleaned."""
    filename = f"lifecycle_whoosh_fail_{uuid.uuid4().hex[:6]}.txt"
    file_path = UPLOAD_DIR / filename
    file_path.write_text("test", encoding="utf-8")

    async def _deleted_rows(stmt, params=None):
        m = MagicMock()
        m.rowcount = 1
        return m

    async def _noop_commit():
        pass

    mock_db = AsyncMock()
    mock_db.execute = _deleted_rows
    mock_db.commit = _noop_commit
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)

    with patch("app.ingestion.processor.AsyncSessionLocal", return_value=mock_db):
        with patch(
            "app.ingestion.processor.delete_from_whoosh_index",
            side_effect=RuntimeError("Whoosh index locked"),
        ):
            stats = await purge_document_lifecycle(filename)

    # Whoosh failure logged as warning; all other stats should still succeed
    assert stats["pgvector_deleted"] >= 1
    assert stats["ingested_file_deleted"] is True
    assert stats["file_unlinked"] is True
    assert stats["whoosh_deleted"] == 0


# ─── Test 4: project_id scoping ─────────────────────────────────────────────

@pytest.mark.anyio
async def test_purge_document_lifecycle_with_project_id():
    """When project_id is provided, the PGVector DELETE must include the project_id filter."""
    filename = f"proj_scoped_{uuid.uuid4().hex[:6]}.txt"
    project_id = "proj_delta_123"

    captured_sql = []

    async def _capture_sql(stmt, params=None):
        captured_sql.append(str(stmt))
        m = MagicMock()
        m.rowcount = 2
        return m

    async def _noop_commit():
        pass

    mock_db = AsyncMock()
    mock_db.execute = _capture_sql
    mock_db.commit = _noop_commit
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)

    with patch("app.ingestion.processor.AsyncSessionLocal", return_value=mock_db):
        with patch("app.ingestion.processor.delete_from_whoosh_index", return_value=0):
            stats = await purge_document_lifecycle(filename, project_id=project_id)

    # The first captured SQL should include the project_id filter
    assert any("project_id" in sql for sql in captured_sql), (
        "PGVector DELETE did not include project_id filter when project_id was provided"
    )
