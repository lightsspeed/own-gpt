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


def search_knowledge_base_impl(query: str, project_id: str = "") -> str:
    """Read-only: search the RAG knowledge base for uploaded documents."""
    try:
        results = similarity_search(query, k=3, project_id=project_id or None)
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


def web_search_impl(query: str, max_results: int = 5) -> str:
    """Read-only: search the live web via Tavily API for real-time external information.

    Safety Bounds:
    - Query length: max 300 characters
    - Max results: clamped 1..5
    - Request timeout: 10.0 seconds
    - Response size: max 3000 characters total

    Returns formatted structured search results including Title, URL, Domain, and Snippet.
    Fails gracefully if TAVILY_API_KEY is missing or request times out/errors.
    """
    from app.core.config import settings

    api_key = settings.TAVILY_API_KEY.strip()
    if not api_key:
        return "Web search is currently unavailable: TAVILY_API_KEY is not configured in the server environment."

    clean_query = query.strip()[:300]
    if not clean_query:
        return "Web search query cannot be empty."

    clamped_max_results = max(1, min(max_results, 5))

    try:
        import requests
        import re
        from urllib.parse import urlparse

        def _do_search(q: str):
            return requests.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": q,
                    "max_results": clamped_max_results,
                    "search_depth": "basic",
                    "include_answer": False,
                    "include_raw_content": False,
                },
                headers={"Content-Type": "application/json"},
                timeout=10.0,
            )

        resp = _do_search(clean_query)

        # Retry once if Tavily 400 error due to site: operator formatting
        if resp.status_code == 400 and "site:" in clean_query.lower():
            fallback_q = re.sub(r"site:\S+", "", clean_query, flags=re.IGNORECASE).strip()
            if fallback_q:
                resp = _do_search(fallback_q)

        if resp.status_code != 200:
            logger.warning("tavily_search_http_error status=%d body=%s", resp.status_code, resp.text[:200])
            return f"Web search failed (HTTP {resp.status_code}). Please rephrase your query or try again."

        data = resp.json()
        raw_results = data.get("results", [])
        if not raw_results:
            return f"No web search results found for query: '{clean_query}'."

        formatted_items = []
        for i, item in enumerate(raw_results, 1):
            title = item.get("title", "Untitled").strip()
            url = item.get("url", "").strip()
            content = item.get("content", "").strip()[:500]
            domain = urlparse(url).netloc if url else "unknown"

            formatted_items.append(
                f"[{i}] Title: {title}\n"
                f"    URL: {url}\n"
                f"    Domain: {domain}\n"
                f"    Snippet: {content}"
            )

        output = f"Web Search Results for '{clean_query}':\n\n" + "\n\n".join(formatted_items)
        return output[:3000]

    except requests.Timeout:
        logger.warning("tavily_search_timeout query=%r", clean_query[:50])
        return "Web search request timed out after 10 seconds. Please try again."
    except Exception as exc:
        logger.error("tavily_search_failed query=%r error=%s", clean_query[:50], exc)
        return f"Web search encountered an error: {str(exc)[:150]}"



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
