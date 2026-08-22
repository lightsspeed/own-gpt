import logging

# Must patch uuid_utils before any langchain import (DLL blocked by AppLocker)
import app.patch_uuid  # noqa: F401

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from app.core.config import settings
from app.core.database import engine, sync_engine, Base
from app.core.langsmith import setup_langsmith
from app.core.logging_config import setup_logging
from app.core.metrics import record_extraction_enabled, render_metrics
from app.core.migrations import run_migrations
from app.core.observability import RequestLoggingMiddleware
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Structured JSON logging foundation (V2.2 P2.1) — before anything logs.
    setup_logging(settings.LOG_LEVEL)

    # Extraction-enabled info gauge (P2.2) — set once so alerting can tell
    # "disabled by config" from "silently not running".
    record_extraction_enabled()

    # Setup - init LangSmith tracing
    setup_langsmith()

    # Run migrations or create tables.
    # create_all handles brand-new tables; run_migrations idempotently evolves
    # existing tables (ownership, model, message status/sequence, ...).
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    run_migrations(sync_engine)

    # LangGraph checkpointer tables (deferred from module import)
    from app.agent.graph import setup_checkpointer
    setup_checkpointer()

    # Bootstrap: assign legacy (owner-less) conversations to the first user.
    _bootstrap_legacy_owners()

    # Load Whoosh BM25 index (persistent, ~200ms if exists)
    from app.core.whoosh_manager import get_whoosh_retriever
    bm25 = get_whoosh_retriever()
    logger.info("whoosh_loaded doc_count=%d", bm25.doc_count)

    # Start the automation scheduler (runs due jobs on cadence)
    from app.learning.automation.scheduler import scheduler
    scheduler.start()
    logger.info("automation_scheduler_started")

    yield
    # Teardown
    scheduler.stop()
    # Stop accepting memory-extraction work; queued tasks are abandoned safely
    # (single-flight TTL + idempotent writes) and daemon workers never block exit.
    from app.learning.extraction.executor import extraction_executor
    extraction_executor.shutdown()
    await engine.dispose()


def _bootstrap_legacy_owners() -> None:
    """Claim legacy conversations (owner_id NULL) for the single user.

    Before V1.1 there was no identity system, so every conversation is
    unowned. In single-user mode they belong to the fallback user; in
    multi-user mode they are left unclaimed (invisible to all users) and
    can be reassigned manually.
    """
    try:
        from sqlalchemy import select, update

        from app.models.chat import ChatSession
        from app.models.user import User
        from app.core.database import SyncSessionLocal

        with SyncSessionLocal() as db:
            users = db.execute(select(User)).scalars().all()
            if len(users) != 1:
                logger.info("legacy_owner_bootstrap_skipped user_count=%d", len(users))
                return
            unowned = db.execute(
                select(ChatSession).where(ChatSession.owner_id.is_(None)).limit(500)
            ).scalars().all()
            for conv in unowned:
                conv.owner_id = users[0].id
            if unowned:
                db.commit()
                logger.info("legacy_owner_bootstrap_claimed conversations=%d", len(unowned))
    except Exception as exc:
        logger.warning("legacy_owner_bootstrap_failed error=%s", exc)


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Custom GPT Backend with LangGraph and RAG",
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(RequestLoggingMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Predictable error envelope: {"error": {"code", "message"}}.

    Existing callers that raised plain-string details keep a readable
    message in the envelope (code "error"); chat/auth endpoints pass the
    envelope directly.
    """
    detail = exc.detail
    if isinstance(detail, dict) and "error" in detail:
        body = detail
    else:
        body = {"error": {"code": "error", "message": str(detail)}}
    return JSONResponse(status_code=exc.status_code, content=body, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": {"code": "validation_error", "message": "Invalid request", "details": exc.errors()}},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception path=%s error=%s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": {"code": "internal_error", "message": "An internal error occurred"}},
    )


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/metrics")
async def metrics_endpoint():
    """Prometheus exposition for the memory-extraction registry (P2.1)."""
    return Response(
        content=render_metrics(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


from app.api.endpoints import chat, documents, index, system, ingestion, auth
from app.api.endpoints import memory as memory_endpoints
from app.api.endpoints import projects as projects_endpoints
from app.learning.api.telemetry import router as telemetry_router
from app.learning.api.quality import router as quality_router
from app.learning.analytics.api import router as analytics_router
from app.learning.evidence.api import router as evidence_router
from app.learning.experiments.api import router as experiments_router
from app.learning.config.api import router as config_router
from app.learning.operations import router as operations_router
from app.learning.automation.api import router as automation_router
from app.learning.api.capabilities import router as capabilities_router

app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
app.include_router(documents.router, prefix="/api/v1/documents", tags=["documents"])
app.include_router(ingestion.router, prefix="/api/v1", tags=["ingestion"])
app.include_router(index.router, prefix="/api/v1", tags=["index"])
app.include_router(system.router, prefix="/api/v1", tags=["system"])
app.include_router(telemetry_router, prefix="/api/v1", tags=["telemetry"])
app.include_router(quality_router, prefix="/api/v1", tags=["quality"])
app.include_router(analytics_router, prefix="/api/v1", tags=["analytics"])
app.include_router(evidence_router, prefix="/api/v1", tags=["evidence"])
app.include_router(experiments_router, prefix="/api/v1", tags=["experiments"])
app.include_router(config_router, prefix="/api/v1", tags=["config"])
app.include_router(operations_router, prefix="/api/v1", tags=["operations"])
app.include_router(automation_router, prefix="/api/v1", tags=["automation"])
app.include_router(capabilities_router, prefix="/api/v1", tags=["capabilities"])
app.include_router(memory_endpoints.router, prefix="/api/v1/memory", tags=["memory"])
app.include_router(projects_endpoints.router, prefix="/api/v1/projects", tags=["projects"])