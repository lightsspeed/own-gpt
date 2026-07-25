import logging

# Must patch uuid_utils before any langchain import (DLL blocked by AppLocker)
import app.patch_uuid  # noqa: F401

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import engine, Base
from app.core.langsmith import setup_langsmith
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup - init LangSmith tracing
    setup_langsmith()

    # Run migrations or create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Load Whoosh BM25 index (persistent, ~200ms if exists)
    from app.core.whoosh_manager import get_whoosh_retriever
    bm25 = get_whoosh_retriever()
    logger.info("whoosh_loaded doc_count=%d", bm25.doc_count)

    yield
    # Teardown
    await engine.dispose()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Custom GPT Backend with LangGraph and RAG",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

from app.api.endpoints import chat, documents, index, system
from app.learning.api.telemetry import router as telemetry_router
from app.learning.analytics.api import router as analytics_router
from app.learning.evidence.api import router as evidence_router
from app.learning.experiments.api import router as experiments_router
from app.learning.config.api import router as config_router
from app.learning.operations import router as operations_router
from app.learning.automation.api import router as automation_router
from app.learning.api.capabilities import router as capabilities_router

app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(documents.router, prefix="/api/v1", tags=["documents"])
app.include_router(index.router, prefix="/api/v1", tags=["index"])
app.include_router(system.router, prefix="/api/v1", tags=["system"])
app.include_router(telemetry_router, prefix="/api/v1", tags=["telemetry"])
app.include_router(analytics_router, prefix="/api/v1", tags=["analytics"])
app.include_router(evidence_router, prefix="/api/v1", tags=["evidence"])
app.include_router(experiments_router, prefix="/api/v1", tags=["experiments"])
app.include_router(config_router, prefix="/api/v1", tags=["config"])
app.include_router(operations_router, prefix="/api/v1", tags=["operations"])
app.include_router(automation_router, prefix="/api/v1", tags=["automation"])
app.include_router(capabilities_router, prefix="/api/v1", tags=["capabilities"])
