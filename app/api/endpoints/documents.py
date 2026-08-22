from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db
from app.ingestion.processor import SUPPORTED_TYPES, UPLOAD_DIR
import os
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

class DocumentListResponse(BaseModel):
    supported_types: List[str]

@router.get("/supported-types", response_model=DocumentListResponse)
async def get_supported_types():
    return DocumentListResponse(supported_types=list(SUPPORTED_TYPES.keys()))


@router.get("/")
async def list_documents(db: AsyncSession = Depends(get_db)):
    try:
        query = text("""
            SELECT COALESCE(cmetadata->>'filename', cmetadata->>'source', 'unknown') as filename,
                   count(*) as chunks
            FROM langchain_pg_embedding
            GROUP BY COALESCE(cmetadata->>'filename', cmetadata->>'source', 'unknown')
            ORDER BY filename ASC
        """)
        result = await db.execute(query)
        rows = result.fetchall()

        docs = [{"filename": row.filename, "chunks": row.chunks} for row in rows]
        return docs
    except Exception as e:
        logger.error(f"Failed to fetch documents: {e}")
        if "relation \"langchain_pg_embedding\" does not exist" in str(e):
            return []
        raise HTTPException(status_code=500, detail=str(e))


class ChunkContent(BaseModel):
    chunk_index: int
    content: str
    char_count: int

class DocumentContentResponse(BaseModel):
    filename: str
    total_chunks: int
    total_chars: int
    chunks: List[ChunkContent]


@router.get("/{filename:path}/content", response_model=DocumentContentResponse)
async def get_document_content(filename: str, db: AsyncSession = Depends(get_db)):
    try:
        query = text("""
            SELECT cmetadata, document
            FROM langchain_pg_embedding
            WHERE cmetadata->>'filename' = :filename
               OR cmetadata->>'source' = :filename2
            ORDER BY (cmetadata->>'chunk_index')::integer ASC NULLS LAST
        """)
        result = await db.execute(query, {"filename": filename, "filename2": filename})
        rows = result.fetchall()

        chunks = []
        total_chars = 0
        for idx, row in enumerate(rows):
            content = row.document or ""
            char_count = len(content)
            total_chars += char_count
            meta = row.cmetadata or {}
            chunks.append(ChunkContent(
                chunk_index=meta.get("chunk_index", idx),
                content=content,
                char_count=char_count,
            ))

        return DocumentContentResponse(
            filename=filename,
            total_chunks=len(chunks),
            total_chars=total_chars,
            chunks=chunks,
        )
    except Exception as e:
        logger.error(f"Failed to fetch document content for {filename}: {e}")
        if "relation \"langchain_pg_embedding\" does not exist" in str(e):
            raise HTTPException(status_code=404, detail="No documents found. Upload a document first.")
        raise HTTPException(status_code=500, detail=str(e))


class ChunkByIndexResponse(BaseModel):
    filename: str
    chunk_index: int
    content: str
    page: int | None
    section: str | None
    total_chunks: int


@router.get("/{filename:path}/chunks/{chunk_index}", response_model=ChunkByIndexResponse)
async def get_chunk_by_index(filename: str, chunk_index: int, db: AsyncSession = Depends(get_db)):
    """Fetch a single chunk by its document chunk_index.

    Used by the Source Inspector modal to display the exact supporting chunk.
    Falls back gracefully if the chunk or document no longer exists (404).
    """
    try:
        # Try the exact chunk_index first
        query = text("""
            SELECT cmetadata, document
            FROM langchain_pg_embedding
            WHERE (cmetadata->>'filename' = :filename OR cmetadata->>'source' = :filename2)
              AND (cmetadata->>'chunk_index')::int = :chunk_index
            LIMIT 1
        """)
        result = await db.execute(query, {
            "filename": filename,
            "filename2": filename,
            "chunk_index": chunk_index,
        })
        row = result.fetchone()

        # Count total chunks for this document
        count_query = text("""
            SELECT count(*)
            FROM langchain_pg_embedding
            WHERE cmetadata->>'filename' = :filename OR cmetadata->>'source' = :filename2
        """)
        total = (await db.execute(count_query, {"filename": filename, "filename2": filename})).scalar() or 0

        if row is None:
            raise HTTPException(
                status_code=404,
                detail=f"Chunk {chunk_index} not found for document '{filename}'."
            )

        meta = row.cmetadata or {}
        page_val = meta.get("page")
        try:
            page_val = int(page_val) if page_val is not None else None
        except (ValueError, TypeError):
            page_val = None

        section_val = meta.get("chapter") or meta.get("section") or None

        return ChunkByIndexResponse(
            filename=filename,
            chunk_index=chunk_index,
            content=row.document or "",
            page=page_val,
            section=section_val,
            total_chunks=int(total),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch chunk {chunk_index} for {filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{filename:path}/exists")
async def document_exists(filename: str, db: AsyncSession = Depends(get_db)):
    """Check whether a document is still present in the knowledge base.

    Returns {exists: bool, chunk_count: int}. Used by SourceInspectorModal
    to gracefully handle documents that have been deleted after citation.
    """
    try:
        count_query = text("""
            SELECT count(*)
            FROM langchain_pg_embedding
            WHERE cmetadata->>'filename' = :filename OR cmetadata->>'source' = :filename2
        """)
        total = (await db.execute(count_query, {"filename": filename, "filename2": filename})).scalar() or 0
        return {"exists": int(total) > 0, "chunk_count": int(total)}
    except Exception as e:
        logger.error(f"Failed to check existence for {filename}: {e}")
        return {"exists": False, "chunk_count": 0}


class PageContent(BaseModel):
    page_number: int
    text: str

class DocumentPagesResponse(BaseModel):
    filename: str
    total_pages: int
    pages: List[PageContent]


@router.get("/{filename:path}/pages", response_model=DocumentPagesResponse)
async def get_document_pages(filename: str):
    ext = os.path.splitext(filename)[-1].lower()
    file_path = UPLOAD_DIR / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Original file not found.")

    try:
        if ext == ".pdf":
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(file_path.read_bytes())
                tmp_path = tmp.name
            loader = PyPDFLoader(tmp_path)
            docs = loader.load()
            pages = []
            for i, doc in enumerate(docs):
                text = (doc.page_content or "").replace("\x00", "")
                pages.append(PageContent(page_number=i + 1, text=text))
            os.unlink(tmp_path)
            return DocumentPagesResponse(
                filename=filename,
                total_pages=len(pages),
                pages=pages,
            )
        else:
            text = file_path.read_text(encoding="utf-8", errors="replace")
            return DocumentPagesResponse(
                filename=filename,
                total_pages=1,
                pages=[PageContent(page_number=1, text=text)],
            )
    except Exception as e:
        logger.error(f"Failed to extract pages for {filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{filename:path}/file")
async def get_original_file(filename: str):
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Original file not found.")
    ext = os.path.splitext(filename)[-1].lower()
    media_type = SUPPORTED_TYPES.get(ext, "application/octet-stream")
    return FileResponse(path=str(file_path), media_type=media_type, filename=filename)


@router.delete("/{filename:path}")
async def delete_document(filename: str, db: AsyncSession = Depends(get_db)):
    try:
        from app.ingestion.processor import purge_document_lifecycle
        stats = await purge_document_lifecycle(filename)
        return {
            "status": "success",
            "message": f"Successfully deleted {filename} and synchronized document lifecycle.",
            "stats": stats,
        }
    except Exception as e:
        logger.error(f"Failed to delete document {filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
