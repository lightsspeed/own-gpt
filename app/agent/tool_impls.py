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


def remember_user_fact_impl(fact: str, user_id: str = "", project_id: str = "") -> str:
    """Mutating: persist a user fact into governed long-term memory.

    Routes through the V2.1 MemoryService (single authority): source
    user_declared → status active, authority explicit_user, confidence 0.95.
    The graph injects user_id/project_id from the request tenant context.
    """
    if not user_id:
        return "Cannot save fact: no authenticated user context."
    from app.core.database import SyncSessionLocal
    from app.models.memory import DOMAIN_SEMANTIC, SOURCE_USER_DECLARED
    from app.services import memory as mem

    try:
        with SyncSessionLocal() as db:
            entity = mem.create_memory(
                db,
                user_id=user_id,
                statement=fact,
                domain=DOMAIN_SEMANTIC,
                source=SOURCE_USER_DECLARED,
                project_id=project_id or None,
            )
            return f"Successfully saved fact to long-term memory ({entity.id}): '{entity.statement}'"
    except Exception as e:
        return f"Failed to save fact to memory: {str(e)}"


def remember_session_fact_impl(fact: str, session_id: str = "", user_id: str = "", project_id: str = "") -> str:
    """Mutating: persist a fact scoped to the current project (this session).

    V2.1 has no session scope — the current conversation's project is the
    natural scope, and the fact is still user-declared (active, explicit_user).
    """
    if not user_id:
        return "Cannot save fact: no authenticated user context."
    from app.core.database import SyncSessionLocal
    from app.models.memory import DOMAIN_SEMANTIC, SOURCE_USER_DECLARED
    from app.services import memory as mem

    try:
        with SyncSessionLocal() as db:
            entity = mem.create_memory(
                db,
                user_id=user_id,
                statement=fact,
                domain=DOMAIN_SEMANTIC,
                source=SOURCE_USER_DECLARED,
                project_id=project_id or None,
                source_conversation_id=session_id or None,
            )
            return f"Successfully saved fact to conversation memory ({entity.id}): '{entity.statement}'"
    except Exception as e:
        return f"Failed to save fact to memory: {str(e)}"


def forget_user_fact_impl(fact: str, session_id: str = "", user_id: str = "", project_id: str = "") -> str:
    """Mutating: logically delete an active memory matching the given text.

    Exact normalized-statement match in the project scope (falling back to
    user-wide scope), then V2.1 logical delete (status=deleted + audit event).
    """
    if not user_id:
        return "Cannot forget fact: no authenticated user context."
    from app.core.database import SyncSessionLocal
    from app.services import memory as mem

    try:
        with SyncSessionLocal() as db:
            target = mem.find_memory_by_statement(
                db, user_id, fact, project_id=project_id or None
            )
            if target is None:
                return f"No matching memory found for: '{fact}'. Nothing was forgotten."
            entity = mem.delete_memory(
                db, target.id, user_id, actor="agent_tool",
                note="forgotten via forget_user_fact tool",
            )
            return f"Successfully forgotten ({entity.id}): '{entity.statement}'"
    except Exception as e:
        return f"Failed to forget fact: {str(e)}"
