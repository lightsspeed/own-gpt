"""
LangSmith Tracing Setup

Sets up the LangSmith client for observability across the entire pipeline.
- Environment-based auto-tracing already covers LangChain calls (LLM, vector store, graph)
- This module adds explicit client initialization + helpers for custom pipeline stage tracing
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

_client = None


def get_client():
    global _client
    if _client is None:
        try:
            from langsmith import Client
            _client = Client(
                api_url=settings.LANGCHAIN_ENDPOINT,
                api_key=settings.LANGCHAIN_API_KEY,
            )
            logger.info("langsmith_client_initialized project=%s endpoint=%s",
                        settings.LANGCHAIN_PROJECT, settings.LANGCHAIN_ENDPOINT)
        except Exception as exc:
            logger.warning("langsmith_client_init_failed error=%s", exc)
    return _client


def traceable(name: Optional[str] = None, metadata: Optional[dict] = None):
    """
    Decorator to trace any pipeline function as a LangSmith run.
    Falls back silently — never breaks the pipeline.

    Usage:
        @traceable(name="intent_classify")
        def my_stage(query: str) -> Result: ...
    """
    try:
        from langsmith import traceable as _langsmith_traceable
        return _langsmith_traceable(name=name, metadata=metadata)
    except ImportError:
        def passthrough(fn: Callable) -> Callable:
            return fn
        return passthrough


def create_trace(
    name: str,
    run_type: str = "chain",
    inputs: Optional[dict] = None,
    parent_run: Optional[Any] = None,
    metadata: Optional[dict] = None,
):
    """
    Create a LangSmith RunTree for manual tracing of non-LangChain stages.

    Usage:
        with create_trace("reranker", run_type="chain", inputs={"query": q}) as run:
            result = my_function()
            run.end(outputs={"result": result})
    """
    try:
        from langsmith.run_trees import RunTree
        client = get_client()
        run = RunTree(
            name=name,
            run_type=run_type,
            inputs=inputs or {},
            parent_run=parent_run,
            client=client,
            metadata=metadata or {},
        )
        return run
    except Exception as exc:
        logger.warning("langsmith_create_trace_failed name=%s error=%s", name, exc)

        class _NoopRun:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def end(self, **kwargs): pass
            def add_child(self, **kwargs): pass

        return _NoopRun()


def setup_langsmith():
    """
    One-time setup: validate env vars, init client, log status.
    Called from main.py lifespan startup.
    """
    if not settings.LANGCHAIN_API_KEY:
        logger.warning("langsmith_disabled LANGCHAIN_API_KEY not set")
        return False

    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_ENDPOINT", settings.LANGCHAIN_ENDPOINT)
    os.environ.setdefault("LANGCHAIN_PROJECT", settings.LANGCHAIN_PROJECT)
    os.environ.setdefault("LANGCHAIN_API_KEY", settings.LANGCHAIN_API_KEY)

    client = get_client()
    if client is None:
        logger.warning("langsmith_setup_incomplete")
        return False

    logger.info(
        "langsmith_ready project=%s endpoint=%s",
        settings.LANGCHAIN_PROJECT,
        settings.LANGCHAIN_ENDPOINT,
    )
    return True
