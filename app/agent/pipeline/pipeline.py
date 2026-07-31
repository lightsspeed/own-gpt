"""
RAG Pipeline Orchestrator

This module is the only entry point the rest of the application needs.
It orchestrates all pipeline stages in order and produces a PipelineContext
that carries all intermediate state for the LangGraph agent.

Stage execution order:
  1. Intent Classification   — what kind of request is this?
  2. Request Routing         — do we need retrieval?
  3. Query Rewriting         — can we improve the query for retrieval?
  4. Knowledge Retrieval     — similarity_search_with_score, top-20
  5. Cross-Encoder Reranking — FlashRank, top-5
  6. Confidence Evaluation   — composite score → answer/web/clarify decision
  7. Context Construction    — formatted context string for the LLM prompt
  -- LangGraph Agent runs here --
  8. Response Validation     — rule-based → LLM escalation if needed
  9. Tracing                 — store full trace to Redis

Design principles:
  - Each stage is independently testable (see tests/)
  - pipeline.py only orchestrates — no business logic here
  - Configuration via pipeline_config.yaml — no hardcoded values
  - All stages log start, end, latency, and decision
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import List, Optional

from app.core.langsmith import traceable
from .confidence import ConfidenceEvaluator, ConfidenceResult
from .intent import Intent, IntentClassifier, IntentResult
from .planner import Planner, AnswerMode
from .evidence_builder import EvidenceBuilder, EvidenceBuilderResult
from .reranker import CrossEncoderReranker, RankedChunk
from .retriever import Retriever, RetrievedChunk
from .rewrite import QueryRewriter, RewriteResult
from .router import RequestRouter, RouterResult, RouteDecision
from .tracing import PipelineTrace, TracingService
from .validation import ResponseValidator, ValidationResult
from .claim_extractor import ClaimExtractor, Claim
from .grounding_validator import GroundingValidator, GroundingResult

logger = logging.getLogger(__name__)

_CLARIFICATION_MESSAGE = (
    "I don't have enough information to answer your question confidently. "
    "Could you provide more context or rephrase your question?"
)


@dataclass
class PipelineContext:
    """
    Carries all pipeline state through every stage and into the LangGraph agent.
    Passed from the FastAPI endpoint to the LangGraph initial state.
    """
    # Input
    question: str
    session_id: str

    # Stage outputs (populated as pipeline runs)
    intent: Optional[IntentResult] = None
    route: Optional[RouterResult] = None
    source_policy: Optional[AnswerMode] = None
    rewrite: Optional[RewriteResult] = None
    retrieved_chunks: List[RetrievedChunk] = field(default_factory=list)
    ranked_chunks: List[RankedChunk] = field(default_factory=list)
    confidence: Optional[ConfidenceResult] = None

    # The final query used for retrieval (after rewriting)
    final_query: str = ""

    # Formatted context string injected into the system prompt
    context_text: str = ""

    # Answer transparency
    answer_mode: str = "grounded"  # "grounded" | "hybrid" | "synthesis" | "no_evidence"
    answer_mode_metadata: dict = field(default_factory=lambda: {
        "chunk_count": 0,
        "doc_count": 0,
        "confidence": 0.0,
    })

    # Grounding (claim-level validation)
    grounding_result: Optional[GroundingResult] = None

    # Tracing
    trace: Optional[PipelineTrace] = None
    _start_time: float = field(default_factory=time.monotonic)

    @property
    def intent_label(self) -> str:
        return self.intent.intent.value if self.intent else "unknown"

    @property
    def confidence_decision(self) -> str:
        return self.confidence.decision if self.confidence else "unknown"

    @property
    def skip_retrieval(self) -> bool:
        return self.route.skip_retrieval if self.route else True


class RAGPipeline:
    """
    Production RAG pipeline orchestrator.

    Usage:
        pipeline = RAGPipeline(vector_store, redis_url=settings.REDIS_URL, config=cfg)
        ctx = pipeline.process(question="...", session_id="...")
        # ... run LangGraph agent using ctx.context_text and ctx.intent_label ...
        validation = pipeline.validate_response(question, response, ctx)
    """

    def __init__(
        self,
        vector_store,
        bm25_retriever=None,
        redis_url: Optional[str] = None,
        config: Optional[dict] = None,
        embed_fn = None,
    ) -> None:
        cfg = config or {}

        self._intent_classifier = IntentClassifier(
            model_name=cfg.get("intent_model", "gpt-4o-mini"),
        )
        self._router = RequestRouter()
        self._planner = Planner()
        self._rewriter = QueryRewriter(
            model_name=cfg.get("rewrite_model", "gpt-4o-mini"),
        )

        # Store individual retrievers for mode-switching support
        self._vector_retriever = Retriever(
            vector_store=vector_store,
            k=cfg.get("retrieval_k", 20),
        )
        self._bm25_retriever = bm25_retriever

        # Build hybrid retriever (vector + BM25) if BM25 retriever is available
        if bm25_retriever is not None:
            from app.retrievers.hybrid import HybridRetriever
            self._retriever = HybridRetriever(
                vector_retriever=self._vector_retriever,
                bm25_retriever=bm25_retriever,
                top_k_vector=cfg.get("retrieval_k", 20),
                top_k_bm25=cfg.get("hybrid", {}).get("top_k_bm25", 20),
                final_top_k=cfg.get("retrieval_k", 20),
                rrf_k=cfg.get("fusion", {}).get("k", 60),
                similarity_threshold=cfg.get("search", {}).get("similarity_threshold", 0.72),
            )
        else:
            self._retriever = self._vector_retriever

        self._reranker = CrossEncoderReranker(
            top_k=cfg.get("rerank_top_k", 5),
            model_name=cfg.get("reranker_model", "ms-marco-MiniLM-L-12-v2"),
            cache_dir=cfg.get("reranker_cache_dir", "/app/.cache/flashrank"),
        )
        self._confidence = ConfidenceEvaluator(
            high_threshold=cfg.get("confidence_high", 0.70),
            medium_threshold=cfg.get("confidence_medium", 0.45),
        )
        self._validator = ResponseValidator(
            model_name=cfg.get("validation_model", "gpt-4o-mini"),
        )
        self._evidence_builder = EvidenceBuilder(
            min_overlap=cfg.get("evidence", {}).get("min_overlap", 0.15),
        )
        self._claim_extractor = ClaimExtractor()
        self._grounding_validator = GroundingValidator(
            embed_fn=embed_fn or (lambda texts: [[0.0] * 1536 for _ in texts]),
        )
        self._tracer = TracingService(
            redis_url=redis_url,
            ttl_seconds=int(cfg.get("trace_ttl_days", 7)) * 86400,
        )
        self._cfg = cfg

    # ── Main pipeline entry point ────────────────────────────────────────────

    def _select_retriever(self, mode: Optional[str] = None):
        """Select retriever based on mode: hybrid, vector, bm25, or default."""
        if mode == "vector":
            return self._vector_retriever
        elif mode == "bm25" and self._bm25_retriever is not None:
            return self._bm25_retriever
        elif mode == "hybrid" and hasattr(self._retriever, "_bm25"):
            return self._retriever
        return self._retriever

    @traceable(name="rag_pipeline", metadata={"stage": "1-7"})
    def process(self, question: str, session_id: str, retriever_mode: Optional[str] = None, filename: Optional[str] = None) -> PipelineContext:
        """
        Run the full pre-processing pipeline (Stages 1–7).
        Returns a PipelineContext ready to be passed into the LangGraph agent.

        Args:
            question: The user's query.
            session_id: Unique session identifier.
            retriever_mode: "vector" | "bm25" | "hybrid" | None (default).
            filename: If set, restrict retrieval to chunks from this document.
        """
        ctx = PipelineContext(question=question, session_id=session_id)
        trace = PipelineTrace(session_id=session_id, question=question)
        ctx.trace = trace

        logger.info("pipeline_start session_id=%s question=%r", session_id, question[:80])

        # ── Stage 1: Intent Classification ──────────────────────────────────
        t1 = time.monotonic()
        if self._cfg.get("intent_enabled", True):
            ctx.intent = self._intent_classifier.classify(question)
        else:
            from .intent import Intent, IntentResult
            ctx.intent = IntentResult(
                intent=Intent.UNKNOWN,
                confidence=0.5,
                reason="disabled",
                latency_ms=0.0,
                used_llm=False,
            )
        trace.intent_ms = round((time.monotonic() - t1) * 1000, 2)
        trace.intent = ctx.intent.intent.value
        trace.intent_confidence = ctx.intent.confidence
        trace.intent_used_llm = ctx.intent.used_llm

        # ── Stage 2: Request Routing ─────────────────────────────────────────
        t2 = time.monotonic()
        ctx.route = self._router.route(ctx.intent)
        trace.route_decision = ctx.route.decision.value

        # ── Stage 2b: Planner (determines what sources are needed) ────────────
        ctx.source_policy = self._planner.plan(ctx.intent, ctx.route)
        trace.source_policy = ctx.source_policy.policy.value
        trace.answer_mode = ctx.source_policy.policy.value
        trace.requires_evidence = ctx.source_policy.contract.requires_evidence
        trace.min_evidence = ctx.source_policy.contract.min_evidence

        # ── Stage 3: Query Rewriting ─────────────────────────────────────────
        t3 = time.monotonic()
        if self._cfg.get("rewrite_enabled", True) and not ctx.route.skip_retrieval:
            ctx.rewrite = self._rewriter.rewrite(question, ctx.intent)
            trace.rewritten_query = ctx.rewrite.rewritten
            trace.expanded_queries = ctx.rewrite.expanded
            trace.was_rewritten = ctx.rewrite.was_rewritten
            ctx.final_query = ctx.rewrite.rewritten
        else:
            ctx.final_query = question
        trace.rewrite_ms = round((time.monotonic() - t3) * 1000, 2)

        # ── Stages 4 & 5: Retrieval + Reranking ─────────────────────────────
        if not ctx.route.skip_retrieval:
            # Stage 4: Retrieval (mode-switchable: hybrid / vector / bm25)
            if filename:
                # Document-scoped chat: vector-only, BM25 has no source filter
                current_retriever = self._vector_retriever
            else:
                current_retriever = self._select_retriever(retriever_mode)
            t4 = time.monotonic()
            ctx.retrieved_chunks, retrieval_timings = current_retriever.retrieve(ctx.final_query, filename=filename)
            trace.retrieval_time_ms = round((time.monotonic() - t4) * 1000, 2)
            trace.num_retrieved = len(ctx.retrieved_chunks)
            trace.retrieval_scores = [c.score for c in ctx.retrieved_chunks[:10]]
            trace.chunk_ids = [c.metadata_dict().get("chunk_id", "") for c in ctx.retrieved_chunks[:10] if hasattr(c, "metadata_dict")]
            trace.pages = [c.page for c in ctx.retrieved_chunks[:10] if hasattr(c, "page") and c.page is not None]
            trace.chapters = [c.chapter for c in ctx.retrieved_chunks[:10] if hasattr(c, "chapter") and c.chapter is not None]
            trace.retriever_type = retriever_mode or ("hybrid" if hasattr(current_retriever, "_bm25") else "vector")
            trace.vector_search_ms = retrieval_timings.get("vector_search_ms", 0)
            trace.bm25_ms = retrieval_timings.get("bm25_ms", 0)
            trace.rrf_ms = retrieval_timings.get("rrf_ms", 0)

            if ctx.retrieved_chunks:
                # Stage 5: Cross-encoder reranking
                t5 = time.monotonic()
                ctx.ranked_chunks = self._reranker.rerank(
                    ctx.final_query, ctx.retrieved_chunks
                )
                trace.reranker_ms = round((time.monotonic() - t5) * 1000, 2)

                # ── Filter out irrelevant chunks (low reranker score < 0.05 or 0 token overlap) ──
                # When scoped to a document, skip the reranker floor — retrieval is already
                # restricted to the correct file and cross-encoder scores are unreliable per-doc.
                _STOP_WORDS = {
                    "a", "an", "the", "in", "on", "of", "to", "for", "with", "is", "are", "was",
                    "were", "be", "been", "being", "have", "has", "had", "do", "does", "did",
                    "what", "how", "who", "where", "when", "why", "which", "give", "me", "tell",
                    "about", "show", "can", "you", "please", "find", "details", "information",
                    "explain", "describe", "overview", "introduction", "list", "game", "topic",
                }
                question_words = set(re.findall(r"\w+", ctx.question.lower()))
                meaningful_q_tokens = {w for w in question_words if w not in _STOP_WORDS and len(w) > 2}

                filtered: list = []
                for rc in ctx.ranked_chunks:
                    if not filename and rc.reranker_score is not None and rc.reranker_score < 0.05:
                        logger.info(
                            "filtering_low_reranker_chunk session_id=%s score=%.4f source=%s",
                            session_id, rc.reranker_score, rc.chunk.source,
                        )
                        continue

                    if filename:
                        # Document-scoped chat: skip the token-overlap filter. Retrieval is
                        # already restricted to the correct file, and follow-up questions are
                        # referential ("what topic does it cover?") with no shared vocabulary.
                        filtered.append(rc)
                        continue

                    chunk_text = rc.chunk.document.page_content.lower()
                    chunk_words = set(re.findall(r"\w+", chunk_text))

                    if meaningful_q_tokens:
                        overlap = len(meaningful_q_tokens & chunk_words)
                        if overlap >= 1:
                            filtered.append(rc)
                        else:
                            logger.info(
                                "filtering_irrelevant_chunk session_id=%s overlap=0/%d source=%s",
                                session_id, len(meaningful_q_tokens), rc.chunk.source,
                            )
                    else:
                        filtered.append(rc)
                ctx.ranked_chunks = filtered
                trace.num_reranked = len(ctx.ranked_chunks)
                trace.reranker_scores = [c.reranker_score for c in ctx.ranked_chunks]

        # ── Stage 6: Confidence Evaluation ───────────────────────────────────
        t6 = time.monotonic()
        if ctx.route.skip_retrieval:
            # Clamp confidence when no retrieval — model memory/web alone
            # cannot have the same certainty as grounded evidence.
            ctx.confidence = ConfidenceResult(
                overall=0.65,
                retrieval_score=0.0,
                reranker_score=0.0,
                intent_confidence=ctx.intent.confidence if ctx.intent else 1.0,
                source_agreement=0.0,
                decision="answer",
            )
        else:
            ctx.confidence = self._confidence.evaluate(ctx.ranked_chunks, ctx.intent)
        trace.confidence_ms = round((time.monotonic() - t6) * 1000, 2)
        trace.confidence_overall = ctx.confidence.overall
        trace.confidence_decision = ctx.confidence.decision

        # ── Stage 7: Context Construction ────────────────────────────────────
        t7 = time.monotonic()
        ctx.context_text = self._build_context(ctx)
        trace.context_ms = round((time.monotonic() - t7) * 1000, 2)

        # ── Answer Transparency Mode ─────────────────────────────────────────
        if ctx.route.skip_retrieval:
            ctx.answer_mode = "synthesis"
        elif ctx.confidence.decision == "clarification" or not ctx.ranked_chunks:
            ctx.answer_mode = "no_evidence"
        else:
            unique_sources = len({c.chunk.source for c in ctx.ranked_chunks})
            unique_pages = len({
                c.chunk.page for c in ctx.ranked_chunks
                if hasattr(c.chunk, "page") and c.chunk.page is not None
            })
            needs_synthesis = (
                unique_sources > 1
                or (unique_pages > 2 and len(ctx.ranked_chunks) >= 3)
            )
            ctx.answer_mode = "hybrid" if needs_synthesis else "grounded"

        ctx.answer_mode_metadata = {
            "chunk_count": len(ctx.ranked_chunks),
            "doc_count": len({c.chunk.source for c in ctx.ranked_chunks}) if ctx.ranked_chunks else 0,
            "confidence": round(ctx.confidence.overall, 4) if ctx.confidence else 0.0,
            "retrieval_method": trace.retriever_type if trace.retriever_type else ("none" if ctx.route.skip_retrieval else "hybrid"),
        }

        # Enrich LangSmith / trace metadata with timing breakdown
        trace.extra["timing_breakdown"] = {
            "intent_ms": trace.intent_ms,
            "rewrite_ms": trace.rewrite_ms,
            "vector_search_ms": trace.vector_search_ms,
            "bm25_ms": trace.bm25_ms,
            "rrf_ms": trace.rrf_ms,
            "reranker_ms": trace.reranker_ms,
            "confidence_ms": trace.confidence_ms,
            "context_ms": trace.context_ms,
            "stage_1_7_ms": round((time.monotonic() - ctx._start_time) * 1000, 2),
        }

        logger.info(
            "pipeline_complete session_id=%s intent=%s route=%s confidence=%.3f decision=%s",
            session_id,
            ctx.intent_label,
            ctx.route.decision.value,
            ctx.confidence.overall,
            ctx.confidence_decision,
        )
        return ctx

    # ── Post-processing: Validation + Grounding + Tracing ──────────────────

    def run_grounding(
        self,
        response: str,
        ctx: PipelineContext,
    ) -> GroundingResult:
        """Extract claims and validate grounding. Stores result in ctx."""
        claims = self._claim_extractor.extract(response)
        threshold = None
        strict = True
        if ctx.source_policy:
            threshold = {
                "remove": GroundingValidator.STRICT_THRESHOLD,
                "mark": GroundingValidator.HYBRID_THRESHOLD,
                "flag": GroundingValidator.STRICT_THRESHOLD,
                "keep": None,
            }.get(ctx.source_policy.contract.on_unsupported, None)
            strict = ctx.source_policy.contract.on_unsupported in ("remove", "flag")
        result = self._grounding_validator.validate(
            claims=claims,
            chunks=ctx.ranked_chunks,
            threshold=threshold,
            strict=strict,
        )
        ctx.grounding_result = result
        return result

    @traceable(name="pipeline_validate", metadata={"stage": "8-9"})
    def validate_response(
        self,
        question: str,
        response: str,
        ctx: PipelineContext,
    ) -> ValidationResult:
        """
        Stage 8: Validate the LLM response.
        Stage 8b: Grounding validation (claim-level).
        Stage 9: Store the completed trace to Redis.
        """
        t8 = time.monotonic()
        if self._cfg.get("validation_enabled", True):
            result = self._validator.validate(question, response)
        else:
            result = ValidationResult(valid=True, reason="disabled", used_llm=False, latency_ms=0.0)

        # Stage 8b: Grounding validation
        if ctx.ranked_chunks and ctx.source_policy and ctx.source_policy.contract.requires_evidence:
            grounding_start = time.monotonic()
            grounding = self.run_grounding(response, ctx)
            ctx.trace.grounding_ms = round((time.monotonic() - grounding_start) * 1000, 2)
            ctx.trace.grounding_total_claims = grounding.total_count
            ctx.trace.grounding_unsupported = grounding.unsupported_count
            ctx.trace.grounding_all_supported = grounding.all_supported

        # Finalize trace
        if ctx.trace:
            ctx.trace.validation_ms = round((time.monotonic() - t8) * 1000, 2)
            ctx.trace.validation_valid = result.valid
            ctx.trace.validation_used_llm = result.used_llm
            ctx.trace.final_response_len = len(response)
            ctx.trace.total_latency_ms = round(
                (time.monotonic() - ctx._start_time) * 1000, 2
            )

        if self._cfg.get("trace_enabled", True):
            self._tracer.store(ctx.trace)

        return result

    @property
    def tracer(self) -> TracingService:
        return self._tracer

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _build_context(self, ctx: PipelineContext) -> str:
        """
        Format reranked chunks into a context string for the LLM system prompt.
        Presents clean document source headings without raw internal chunk labels.
        """
        if not ctx.ranked_chunks:
            return ""

        parts: List[str] = []
        for i, rc in enumerate(ctx.ranked_chunks):
            src = getattr(rc.chunk, "source", None) or "document"
            parts.append(
                f"--- Document Source ({src}) ---\n"
                f"{rc.chunk.document.page_content}"
            )
        return "\n\n---\n\n".join(parts)

    @staticmethod
    def clarification_message() -> str:
        return _CLARIFICATION_MESSAGE
