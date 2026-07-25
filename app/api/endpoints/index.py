from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.core.config import settings
from app.core.database import get_db
from app.services.vector_store import vector_store

logger = logging.getLogger(__name__)
router = APIRouter()

_INDEX_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "data", "whoosh")


def _get_bm25():
    try:
        from app.core.whoosh_manager import get_whoosh_retriever
        return get_whoosh_retriever()
    except Exception as exc:
        logger.warning("whoosh_not_available error=%s", exc)
        return None


@router.get("/index/status")
async def index_status():
    bm25 = _get_bm25()
    if bm25 is None:
        return {"doc_count": 0, "index_path": _INDEX_DIR, "index_exists": False, "last_updated": "N/A"}

    index_exists = Path(bm25.index_dir).exists() if hasattr(bm25, "index_dir") else False
    return {
        "doc_count": bm25.doc_count if hasattr(bm25, "doc_count") else 0,
        "index_path": getattr(bm25, "index_dir", _INDEX_DIR),
        "index_exists": index_exists,
        "last_updated": "available",
    }


@router.get("/index/corpus")
async def corpus_manifest(db: AsyncSession = Depends(get_db)):
    """Return the full corpus chunk manifest from pgvector for coverage analysis."""
    try:
        query = text("""
            SELECT COALESCE(cmetadata->>'chunk_id', id::text) AS chunk_id,
                   cmetadata->>'filename' AS filename,
                   cmetadata->>'source' AS source,
                   cmetadata->>'page' AS page,
                   length(document) AS doc_length
            FROM langchain_pg_embedding
            ORDER BY cmetadata->>'filename', id
        """)
        result = await db.execute(query)
        rows = result.fetchall()
        chunks = []
        seen_sources = set()
        for row in rows:
            chunks.append({
                "chunk_id": row.chunk_id,
                "filename": row.filename or "unknown",
                "source": row.source or "unknown",
                "page": row.page,
                "doc_length": row.doc_length or 0,
            })
            if row.filename:
                seen_sources.add(row.filename)

        return {
            "total_chunks": len(chunks),
            "total_sources": len(seen_sources),
            "sources": sorted(seen_sources),
            "chunks": chunks,
        }
    except Exception as e:
        logger.error("Corpus manifest query failed: %s", e)
        if "relation \"langchain_pg_embedding\" does not exist" in str(e):
            return {"total_chunks": 0, "total_sources": 0, "sources": [], "chunks": []}
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/index/rebuild")
async def index_rebuild():
    try:
        from app.core.whoosh_manager import rebuild_whoosh_index
        count = rebuild_whoosh_index(vector_store)
        return {"count": count, "status": "ok"}
    except Exception as exc:
        logger.error("index_rebuild_failed error=%s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
