"""
LearningRecord builder — constructs a LearningRecord from pipeline state.

Called from the chat endpoint after pipeline completion.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.agent.pipeline import PipelineContext
from app.evaluation.reproducibility import _git_commit

from ..models import LearningRecord
from ..pii.sanitizer import sanitize

logger = logging.getLogger(__name__)


def build_learning_record(
    ctx: PipelineContext,
    response: str = "",
    thumb: Optional[str] = None,
) -> LearningRecord:
    """
    Build a LearningRecord from the pipeline context and the final response.

    Args:
        ctx: The fully-populated PipelineContext after all stages 1-9.
        response: The final LLM response text.
        thumb: Optional thumb state ("up", "down", or None).

    Returns:
        A populated LearningRecord ready for storage.
    """
    sanitized = sanitize(ctx.question)
    record = LearningRecord(
        session_id=ctx.session_id,
        question=ctx.question,
        normalized_question=sanitized,
        response=sanitize(response),
        intent=ctx.intent_label if ctx.intent else "unknown",
        matched_rule=ctx.intent.matched_rule if ctx.intent else "",
        intent_confidence=ctx.intent.confidence if ctx.intent else 0.0,
        retriever=ctx.answer_mode_metadata.get("retrieval_method", ""),
        answer_mode=ctx.answer_mode,
        model="gpt-4o-mini",
        latency_ms=ctx.trace.total_latency_ms if ctx.trace else 0.0,
        tokens_in=ctx.trace.prompt_tokens if ctx.trace else 0,
        tokens_out=ctx.trace.completion_tokens if ctx.trace else 0,
        confidence=ctx.confidence.overall if ctx.confidence else 0.0,
        thumb=thumb,
    )

    # ── Retrieval evidence ───────────────────────────────────────────────
    if ctx.retrieved_chunks:
        record.documents = list({
            getattr(c, "source", "") or getattr(c, "filename", "unknown")
            for c in ctx.retrieved_chunks
        })
        record.chunks = [
            {"chunk_id": getattr(c, "chunk_id", ""), "page": getattr(c, "page", None),
             "source": getattr(c, "source", ""), "score": getattr(c, "score", 0.0)}
            for c in ctx.retrieved_chunks[:20]
        ]
        record.vector_scores = [getattr(c, "score", 0.0) for c in ctx.retrieved_chunks[:20]]

    if ctx.ranked_chunks:
        record.reranker_scores = [getattr(c, "reranker_score", 0.0) for c in ctx.ranked_chunks]

    # ── Version metadata ─────────────────────────────────────────────────
    record.git_commit = _git_commit()
    record.embedding_model = ctx.answer_mode_metadata.get("retrieval_method", "")
    record.chunk_size = 512  # default; could be read from config

    # ── Failure detection ────────────────────────────────────────────────
    if ctx.confidence and ctx.confidence.decision == "clarification":
        record.accepted = False
        record.failure_reason = "clarification"
    elif not ctx.ranked_chunks and not ctx.route.skip_retrieval:
        record.accepted = False
        record.failure_reason = "no_evidence"
    elif ctx.confidence and ctx.confidence.overall < 0.45:
        record.failure_reason = "low_confidence"

    return record
