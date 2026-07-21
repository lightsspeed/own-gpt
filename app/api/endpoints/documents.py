from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Any
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.services.vector_store import add_documents_to_store
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db
import tempfile
import os
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

SUPPORTED_TYPES = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
}

class DocumentResponse(BaseModel):
    filename: str
    message: str
    chunks: int
    file_type: str

class DocumentListResponse(BaseModel):
    supported_types: List[str]

@router.get("/supported-types", response_model=DocumentListResponse)
async def get_supported_types():
    return DocumentListResponse(supported_types=list(SUPPORTED_TYPES.keys()))

@router.post("/upload", response_model=DocumentResponse)
async def upload_document(file: UploadFile = File(...)):
    """
    Upload documents for RAG ingestion.
    Supports: PDF, TXT, Markdown files.
    Parses, chunks, embeds, and stores in pgvector.
    """
    ext = os.path.splitext(file.filename)[-1].lower()
    if ext not in SUPPORTED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Supported: {', '.join(SUPPORTED_TYPES.keys())}"
        )

    tmp_path = None
    try:
        content = await file.read()

        # --- Load documents based on file type ---
        if ext == ".pdf":
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            loader = PyPDFLoader(tmp_path)
            docs = loader.load()

        elif ext in (".txt", ".md"):
            text = content.decode("utf-8", errors="replace")
            docs = [Document(
                page_content=text,
                metadata={"source": file.filename, "file_type": ext}
            )]

        # --- Sanitize documents (remove PostgreSQL-incompatible NUL bytes) ---
        for doc in docs:
            if doc.page_content:
                doc.page_content = doc.page_content.replace("\x00", "")

        # --- Chunk ---
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
        )
        splits = splitter.split_documents(docs)

        # Inject filename into metadata for traceability
        for chunk in splits:
            chunk.metadata["filename"] = file.filename

        # --- Embed & store ---
        add_documents_to_store(splits)

        return DocumentResponse(
            filename=file.filename,
            message=f"Successfully embedded {len(splits)} chunks from '{file.filename}'.",
            chunks=len(splits),
            file_type=ext,
        )

    except Exception as e:
        logger.error("Document upload error: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.get("/")
async def list_documents(db: AsyncSession = Depends(get_db)):
    """
    Returns a list of unique uploaded documents by reading the cmetadata field
    from the pgvector table. Groups by filename to count chunks.
    """
    try:
        # Group by the 'filename' key inside the JSONB 'cmetadata' column
        query = text("""
            SELECT cmetadata->>'filename' as filename, count(*) as chunks
            FROM langchain_pg_embedding
            WHERE cmetadata ? 'filename'
            GROUP BY cmetadata->>'filename'
            ORDER BY filename ASC
        """)
        result = await db.execute(query)
        rows = result.fetchall()
        
        docs = [{"filename": row.filename, "chunks": row.chunks} for row in rows]
        return docs
    except Exception as e:
        logger.error(f"Failed to fetch documents: {e}")
        # Table might not exist yet if no uploads have occurred
        if "relation \"langchain_pg_embedding\" does not exist" in str(e):
            return []
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{filename}")
async def delete_document(filename: str, db: AsyncSession = Depends(get_db)):
    """
    Deletes all vector chunks associated with a specific filename.
    """
    try:
        query = text("""
            DELETE FROM langchain_pg_embedding
            WHERE cmetadata->>'filename' = :filename
        """)
        await db.execute(query, {"filename": filename})
        await db.commit()
        return {"status": "success", "message": f"Deleted {filename}"}
    except Exception as e:
        logger.error(f"Failed to delete document {filename}: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

