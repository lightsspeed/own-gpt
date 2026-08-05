"""Tool core implementations — pure, sandbox-executable functions.

Each function here is the real side-effectful (or read-only) body of a tool.
The LangChain tool wrappers in tools.py delegate to these; the sandbox runner
executes them by module+name in an isolated subprocess. Nothing in this module
may depend on the FastAPI app or the agent graph — it must stay importable in
a bare interpreter.
"""

from __future__ import annotations

import logging
from typing import Optional

import redis

from app.services.vector_store import similarity_search
from app.core.config import settings

logger = logging.getLogger(__name__)


def search_knowledge_base_impl(query: str) -> str:
    """Read-only: search the RAG knowledge base for uploaded documents."""
    try:
        results = similarity_search(query, k=3)
        if not results:
            return (
                "No relevant information found in the knowledge base for this query. "
                "The topic is not covered in the Knowledge Base — state this clearly and "
                "do NOT answer using general knowledge."
            )
        context = "\n\n---\n\n".join(
            f"Source: {doc.metadata.get('filename', 'Unknown')}\n{doc.page_content}"
            for doc in results
        )
        return f"Found the following information:\n\n{context}"
    except Exception as e:
        return f"Error searching knowledge base: {str(e)}"


def sm_integration_impl(action: str, target: str, content: Optional[str] = None) -> str:
    """Mock side-effect tool: simulate a social media integration."""
    return f"Mock SM Integration: {action} on {target} succeeded."


def remember_user_fact_impl(fact: str) -> str:
    """Mutating: persist a user fact into long-term memory (Redis)."""
    r = redis.from_url(settings.REDIS_URL)
    r.rpush("user:global:memories", fact)
    return f"Successfully saved fact to long-term memory: '{fact}'"
