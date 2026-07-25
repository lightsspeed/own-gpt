"""
Stage 9: Request Tracing

Purpose: Capture a complete, structured trace of every pipeline execution.
         Traces are the primary debugging and observability tool.

Storage: Redis (already available in the stack)
TTL: 7 days (configurable)

Trace fields:
  trace_id            — unique UUID per request
  session_id          — LangGraph thread ID
  question            — original user query
  intent              — classified intent
  intent_confidence   — classifier confidence [0, 1]
  intent_used_llm     — whether LLM was needed for classification
  rewritten_query     — query after rewriting
  expanded_queries    — alternative query expansions
  route_decision      — routing outcome
  num_retrieved       — number of chunks from pgvector
  retrieval_scores    — individual chunk scores (top-10)
  num_reranked        — chunks returned after reranking
  reranker_scores     — individual reranker scores
  confidence_overall  — composite confidence score
  confidence_decision — answer / web_search / clarification
  memory_used         — was Redis memory retrieved?
  tools_used          — list of LangGraph tool names called
  prompt_tokens       — token usage
  completion_tokens   — token usage
  validation_valid    — did the response pass validation?
  validation_used_llm — did validation escalate to LLM?
  final_response_len  — character count of response
  total_latency_ms    — end-to-end pipeline latency
  timestamp           — Unix timestamp of request
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PipelineTrace:
    # Identifiers
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""

    # Stage 1: Intent
    question: str = ""
    intent: str = ""
    intent_confidence: float = 0.0
    intent_used_llm: bool = False

    # Stage 2: Routing
    route_decision: str = ""

    # Stage 3: Query Rewriting
    rewritten_query: str = ""
    expanded_queries: List[str] = field(default_factory=list)
    was_rewritten: bool = False

    # Stage 4: Retrieval
    num_retrieved: int = 0
    retrieval_scores: List[float] = field(default_factory=list)

    # Stage 5: Reranking
    num_reranked: int = 0
    reranker_scores: List[float] = field(default_factory=list)

    # Stage 6: Confidence
    confidence_overall: float = 0.0
    confidence_decision: str = ""

    # Stage 4/5: Retrieval metadata (enriched for LangSmith)
    chunk_ids: List[str] = field(default_factory=list)
    pages: List[int] = field(default_factory=list)
    chapters: List[str] = field(default_factory=list)
    retrieval_time_ms: float = 0.0
    reranker_time_ms: float = 0.0

    # Per-stage latency breakdown (for observability)
    intent_ms: float = 0.0
    rewrite_ms: float = 0.0
    vector_search_ms: float = 0.0
    bm25_ms: float = 0.0
    rrf_ms: float = 0.0
    reranker_ms: float = 0.0
    confidence_ms: float = 0.0
    context_ms: float = 0.0
    validation_ms: float = 0.0

    # Stage 7: Prompt / Memory
    memory_used: bool = False
    tools_used: List[str] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0

    # Stage 8: Validation
    validation_valid: bool = True
    validation_used_llm: bool = False

    # Response
    final_response_len: int = 0
    total_latency_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)

    # Retrieval config snapshot
    retriever_type: str = ""
    top_k: int = 0
    similarity_threshold: float = 0.0

    # Catch-all for future fields
    extra: Dict[str, Any] = field(default_factory=dict)


class TracingService:
    """
    Persists PipelineTrace objects to Redis with a configurable TTL.
    Organises traces per session for easy history lookup.
    Fails silently — a tracing error must never break the user response.
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        ttl_seconds: int = 60 * 60 * 24 * 7,  # 7 days
    ) -> None:
        self._redis_url = redis_url
        self._ttl = ttl_seconds
        self._redis = None

    def _get_redis(self):
        if self._redis is None and self._redis_url:
            import redis
            self._redis = redis.from_url(self._redis_url)
        return self._redis

    def store(self, trace: PipelineTrace) -> None:
        """Persist a trace to Redis. Silent on failure."""
        try:
            r = self._get_redis()
            if r is None:
                return
            key = f"trace:{trace.session_id}:{trace.trace_id}"
            payload = json.dumps(asdict(trace))
            r.setex(key, self._ttl, payload)
            # Track trace IDs per session (most recent first)
            r.lpush(f"traces:{trace.session_id}", trace.trace_id)
            r.expire(f"traces:{trace.session_id}", self._ttl)
            logger.debug("trace_stored trace_id=%s session_id=%s", trace.trace_id, trace.session_id)
        except Exception as exc:
            logger.warning("trace_store_failed error=%s", exc)

    def get(self, session_id: str, trace_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single trace by ID."""
        try:
            r = self._get_redis()
            if r is None:
                return None
            raw = r.get(f"trace:{session_id}:{trace_id}")
            return json.loads(raw) if raw else None
        except Exception as exc:
            logger.warning("trace_get_failed error=%s", exc)
            return None

    def list_session_traces(self, session_id: str, limit: int = 20) -> List[str]:
        """Return a list of trace IDs for a session (most recent first)."""
        try:
            r = self._get_redis()
            if r is None:
                return []
            return [tid.decode() for tid in r.lrange(f"traces:{session_id}", 0, limit - 1)]
        except Exception as exc:
            logger.warning("trace_list_failed error=%s", exc)
            return []
