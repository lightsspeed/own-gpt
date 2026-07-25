"""
Stage 3: Query Rewriting

Purpose: Improve retrieval quality by reformulating the user's natural-language
         query into a keyword-rich, retrieval-optimized form.

Only runs when:
  intent == rag
  intent == web

Output:
  original        — the raw user query (always preserved)
  rewritten       — the optimized single query
  expanded        — 2-3 alternative phrasings for multi-query retrieval
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import List

from app.core.langsmith import traceable
from .intent import Intent, IntentResult

logger = logging.getLogger(__name__)


@dataclass
class RewriteResult:
    original: str
    rewritten: str
    expanded: List[str] = field(default_factory=list)
    was_rewritten: bool = False
    latency_ms: float = 0.0


_SYSTEM_PROMPT = """You are a search query optimizer for a RAG / web search system.

Given a user's natural-language query, produce:
1. A rewritten version optimized for dense vector retrieval or web search.
   - Remove conversational filler ("can you", "please", "I want to know")
   - Make it keyword-rich and specific (max 15 words)
2. 2-3 expanded alternative queries that capture different facets of the same question.

Return ONLY valid JSON — no markdown, no explanation:
{
  "rewritten": "<optimized query>",
  "expanded": ["<alternative 1>", "<alternative 2>", "<alternative 3>"]
}"""


class QueryRewriter:
    """
    Rewrites and expands user queries for better retrieval.
    Only runs when intent is KNOWLEDGE or WEB — skipped for all other intents.
    """

    _RETRIEVAL_INTENTS = {Intent.KNOWLEDGE, Intent.WEB}

    def __init__(self, model_name: str = "gpt-4o-mini") -> None:
        self._model_name = model_name
        self._llm: object | None = None

    def _get_llm(self):
        if self._llm is None:
            from langchain_openai import ChatOpenAI
            self._llm = ChatOpenAI(model=self._model_name, temperature=0, max_tokens=256)
        return self._llm

    @traceable(name="query_rewrite", metadata={"stage": 3})
    def rewrite(self, query: str, intent: IntentResult) -> RewriteResult:
        """
        Rewrite the query if intent requires retrieval.
        Returns a no-op RewriteResult for intents that skip retrieval.
        """
        # Skip rewriting for non-retrieval intents
        if intent.intent not in self._RETRIEVAL_INTENTS:
            return RewriteResult(
                original=query,
                rewritten=query,
                was_rewritten=False,
            )

        start = time.monotonic()
        from langchain_core.messages import HumanMessage, SystemMessage

        response = self._get_llm().invoke([
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=query),
        ])
        elapsed = round((time.monotonic() - start) * 1000, 2)

        data = json.loads(response.content.strip())
        result = RewriteResult(
            original=query,
            rewritten=data.get("rewritten", query),
            expanded=data.get("expanded", []),
            was_rewritten=True,
            latency_ms=elapsed,
        )

        logger.info(
            "stage=query_rewrite original=%r rewritten=%r expanded_count=%d latency_ms=%.1f",
            result.original,
            result.rewritten,
            len(result.expanded),
            result.latency_ms,
        )
        return result
