from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.services.vector_store import add_documents_to_store
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db
from pathlib import Path
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

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

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
    ext = os.path.splitext(file.filename)[-1].lower()
    if ext not in SUPPORTED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Supported: {', '.join(SUPPORTED_TYPES.keys())}"
        )

    tmp_path = None
    try:
        content = await file.read()

        dest = UPLOAD_DIR / file.filename
        with open(dest, "wb") as f:
            f.write(content)

        if ext == ".pdf":
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            loader = PyPDFLoader(tmp_path)
            docs = loader.load()

        elif ext in (".txt", ".md"):
            text_content = content.decode("utf-8", errors="replace")
            docs = [Document(
                page_content=text_content,
                metadata={"source": file.filename, "file_type": ext}
            )]

        for doc in docs:
            if doc.page_content:
                doc.page_content = doc.page_content.replace("\x00", "")

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
        )
        splits = splitter.split_documents(docs)

        import uuid
        for idx, chunk in enumerate(splits):
            chunk.metadata["filename"] = file.filename
            chunk.metadata["chunk_id"] = str(uuid.uuid4())
            chunk.metadata["chunk_index"] = idx

        ids = [chunk.metadata["chunk_id"] for chunk in splits]
        add_documents_to_store(splits, ids=ids)

        try:
            from app.core.whoosh_manager import add_to_whoosh_index
            add_to_whoosh_index(splits)
        except Exception as whoosh_err:
            logger.warning("whoosh_incremental_update_failed error=%s", whoosh_err)

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
        query = text("""
            DELETE FROM langchain_pg_embedding
            WHERE cmetadata->>'filename' = :filename
               OR cmetadata->>'source' = :filename2
        """)
        await db.execute(query, {"filename": filename, "filename2": filename})
        await db.commit()

        file_path = UPLOAD_DIR / filename
        if file_path.exists():
            file_path.unlink()

        return {"status": "success", "message": f"Deleted {filename}"}
    except Exception as e:
        logger.error(f"Failed to delete document {filename}: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
