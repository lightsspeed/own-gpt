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

from app.services.vector_store import similarity_search
from app.learning.operations.memory import MemoryStore, SCOPE_GLOBAL, session_scope, SOURCE_TOOL_CALL

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
    """Mutating: persist a user fact into long-term memory (global scope)."""
    record = MemoryStore().store_fact(fact, scope=SCOPE_GLOBAL, source=SOURCE_TOOL_CALL)
    return f"Successfully saved fact to long-term memory ({record.id}): '{fact}'"


def remember_session_fact_impl(fact: str, session_id: str = "") -> str:
    """Mutating: persist a fact scoped to the current conversation only."""
    scope = session_scope(session_id) if session_id else SCOPE_GLOBAL
    record = MemoryStore().store_fact(fact, scope=scope, source=SOURCE_TOOL_CALL)
    return f"Successfully saved fact to conversation memory ({record.id}): '{fact}'"


def forget_user_fact_impl(fact: str, session_id: str = "") -> str:
    """Mutating: supersede an active fact matching the given text.

    Searches global scope first, then the current conversation scope.
    """
    store = MemoryStore()
    target = store.find_active_fact(fact, scope=SCOPE_GLOBAL)
    scope_label = "long-term memory"
    if target is None and session_id:
        target = store.find_active_fact(fact, scope=session_scope(session_id))
        scope_label = "conversation memory"
    if target is None:
        return f"No matching memory found for: '{fact}'. Nothing was forgotten."
    store.forget(target.id, operator="agent_tool", note="forgotten via forget_user_fact tool")
    return f"Successfully forgotten {scope_label} ({target.id}): '{target.fact}'"
