from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()

_WHOOSH_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "data", "whoosh"
)


@router.get("/system/status")
async def system_status(db: AsyncSession = Depends(get_db)):
    """Consolidated system health check across all backend services."""
    results: dict[str, Any] = {}

    # PostgreSQL + pgvector
    try:
        pg_result = await db.execute(text("SELECT version() AS ver"))
        pg_version = pg_result.scalar() or ""
        results["postgres"] = {
            "status": "ok",
            "version": pg_version.split(",")[0] if pg_version else "unknown",
        }
    except Exception as e:
        results["postgres"] = {"status": "error", "detail": str(e)}

    # pgvector langchain_pg_embedding table
    try:
        vec_result = await db.execute(
            text("SELECT count(*) AS cnt FROM langchain_pg_embedding")
        )
        vec_count = vec_result.scalar() or 0
        results["pgvector"] = {
            "status": "ok",
            "chunk_count": vec_count,
        }
    except Exception as e:
        results["pgvector"] = {"status": "error", "detail": str(e)}

    # Whoosh BM25 index
    try:
        from app.core.whoosh_manager import get_whoosh_retriever
        bm25 = get_whoosh_retriever()
        doc_count = bm25.doc_count if hasattr(bm25, "doc_count") else 0
        index_dir = getattr(bm25, "index_dir", _WHOOSH_DIR)
        index_exists = Path(index_dir).exists()
        results["whoosh"] = {
            "status": "ok" if index_exists and doc_count > 0 else "degraded",
            "doc_count": doc_count,
            "index_exists": index_exists,
            "index_dir": index_dir,
        }
    except Exception as e:
        results["whoosh"] = {"status": "error", "detail": str(e)}

    # Ollama — local LLM/embedding provider (optional at runtime)
    from app.core.config import settings
    from app.core.llm_provider import LLMProviderError
    try:
        import httpx
        base = settings.OLLAMA_BASE_URL.rstrip("/")
        r = httpx.get(f"{base}/api/tags", timeout=2.0)
        r.raise_for_status()
        tags = [m.get("name", "") for m in r.json().get("models", [])]
        expected = [settings.LLM_MODEL] if settings.LLM_PROVIDER == "ollama" else []
        missing = [m for m in expected if m not in tags]
        results["ollama"] = {
            "status": "ok" if not missing else "degraded",
            "provider": settings.LLM_PROVIDER,
            "base_url": base,
            "models": sorted(tags),
            "missing_models": missing,
        }
    except LLMProviderError as e:
        results["ollama"] = {"status": "error", "detail": str(e)}
    except Exception as e:
        results["ollama"] = {"status": "unavailable", "detail": str(e)}

    return {"status": "ok", "services": results}
