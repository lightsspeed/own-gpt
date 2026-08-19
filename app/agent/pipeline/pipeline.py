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
  (2f) Memory Learning       — V3.8: persist durable explicit user statements via Memory V2 (after validation only)
  9. Tracing                 — store full trace to Redis

Secondary stages (plan-aware path, driven by the LangGraph agent):
  (2b+) Capability Selection — V3.9: match plan steps to existing registered capabilities/tools (before executor)
  (2b+.2) Tool Selection  — V3.11: concrete registered tool + validated arguments per step (before executor)
  (2c') Agent Execution Loop — V3.12: bounded loop, one eligible step per iteration (executor + state update per step)
  (2c)  Execution Policy     — V3.10/3.11: executor treats selections as authoritative; denied steps are blocked (fail closed)

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
from app.core import metrics as core_metrics
from app.agent.contract import map_status
from .trace import AgentTrace, LoggingTraceObserver, record_trace
from .confidence import ConfidenceEvaluator, ConfidenceResult
from .intent import Intent, IntentClassifier, IntentResult
from .planner import Planner, AnswerMode, Plan, PlanStep
from .executor import Executor, ExecutionResult, StepResult
from .synthesizer import Synthesizer, SynthesisResult
from .state import (
    AgentState, StepExecutionState,
    finalize_execution_status, finalize_timing,
)
from .context import ContextOrchestrator, RetrievedContext, ContextRequest
from .evidence_builder import EvidenceBuilder, EvidenceBuilderResult
from .reranker import CrossEncoderReranker, RankedChunk
from .retriever import Retriever, RetrievedChunk
from .rewrite import QueryRewriter, RewriteResult
from .router import RequestRouter, RouterResult, RouteDecision
from .tracing import PipelineTrace, TracingService
from .validation import ResponseValidator, ValidationResult
from .claim_extractor import ClaimExtractor, Claim
from .grounding_validator import GroundingValidator, GroundingResult
from .validator import (
    AnswerValidator,
    SAFE_CLARIFICATION_MESSAGE,
    ValidationResult as AnswerValidationResult,
)
from .learning import AgentLearner, LearningResult
from .capabilities import CapabilitySelector, CapabilitySelection
from .tool_selection import ToolSelector, ToolSelection
from .loop import AgentExecutionLoop, LoopResult
from .cost import (
    TokenBudget,
    DEFAULT_REQUEST_BUDGET_TOKENS,
    DEFAULT_STEP_BUDGET_TOKENS,
)
from .security import (
    record_security,
    sanitize_content,
    sanitize_retrieved_context,
)
from .reliability import (
    IdempotencyLedger,
    ReliabilityGuard,
    TimeoutPolicy,
    DEFAULT_REQUEST_TIMEOUT_S,
    DEFAULT_STEP_TIMEOUT_S,
    DEFAULT_TOOL_TIMEOUT_S,
)

logger = logging.getLogger(__name__)

_CLARIFICATION_MESSAGE = (
    "I don't have enough information to answer your question confidently. "
    "Could you provide more context or rephrase your question?"
)

_KB_NOT_COVERED_MESSAGE = (
    "This topic is not covered in your Knowledge Base. "
    "I can only answer questions based on the documents uploaded to the Knowledge Base. "
    "You can upload relevant documents or rephrase your question."
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
    project_id: Optional[str] = None
    user_id: Optional[str] = None
    filename: Optional[str] = None

    # Stage outputs (populated as pipeline runs)
    intent: Optional[IntentResult] = None
    route: Optional[RouterResult] = None
    plan: Optional[Plan] = None
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

    # V3.3: Execution result (populated after executor runs)
    execution: Optional[ExecutionResult] = None

    # V3.9: Capability selection result (populated before executor runs)
    capability_selections: List[CapabilitySelection] = field(default_factory=list)

    # V3.11: Tool selection result (populated before executor runs)
    tool_selections: List[ToolSelection] = field(default_factory=list)

    # V3.12: Execution loop result (populated by the loop, carries ctx.execution)
    execution_loop: Optional[LoopResult] = None

    # V3.4: Synthesis result (final user-facing answer from executor outputs)
    synthesis: Optional[SynthesisResult] = None

    # V3.6: Context Orchestrator result
    context: Optional[RetrievedContext] = None
    context_request: Optional[ContextRequest] = None

    # V3.5: Structured agent state (observability / tracing)
    agent_state: Optional[AgentState] = None

    # V4.6: Execution identity for StepContext lineage (distinct from
    # request_id — one request may drive one execution run).
    execution_id: Optional[str] = None

    # V4.8: Event-based agent execution trace (passive observability).
    agent_trace: Optional[AgentTrace] = None

    # V4.9: Per-request + per-step token budgets with model-aware estimated
    # cost. Enforcement is passive and happens at LLM call boundaries —
    # a context without a budget behaves exactly as before V4.9.
    token_budget: Optional[TokenBudget] = None

    # V4.11: Reliability & Cancellation. Timeout policy guard (tool / step /
    # request boundaries on an injectable clock) + idempotency ledger
    # (first terminal outcome per execution_id+step_id wins). Cooperative
    # cancellation: the API/operator layer sets cancel_requested; the loop
    # and executor honor it before any new handler starts. All passive —
    # a context without these behaves exactly as before V4.11.
    reliability: Optional[ReliabilityGuard] = None
    idempotency: Optional[IdempotencyLedger] = None
    cancel_requested: bool = False

    # Grounding (claim-level validation)
    grounding_result: Optional[GroundingResult] = None

    # V3.7: Answer validation result (populated after synthesis)
    validation: Optional[AnswerValidationResult] = None

    # V3.8: Memory learning result (populated after validation)
    learning: Optional[LearningResult] = None

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
        learner: Optional[AgentLearner] = None,
        selector: Optional[CapabilitySelector] = None,
        tool_selector: Optional[ToolSelector] = None,
        execution_loop: Optional[AgentExecutionLoop] = None,
    ) -> None:
        cfg = config or {}

        self._intent_classifier = IntentClassifier(
            model_name=cfg.get("intent_model"),
        )
        self._router = RequestRouter()
        self._planner = Planner()
        self._executor = Executor()
        self._synthesizer = Synthesizer()
        self._selector = selector if selector is not None else CapabilitySelector()
        self._tool_selector = tool_selector if tool_selector is not None else ToolSelector()
        self._execution_loop = execution_loop if execution_loop is not None else AgentExecutionLoop()
        self._rewriter = QueryRewriter(
            model_name=cfg.get("rewrite_model"),
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
        self._context_orchestrator = ContextOrchestrator(
            vector_retriever=self._vector_retriever,
            hybrid_retriever=self._retriever,
            reranker=self._reranker,
        )
        self._validator = ResponseValidator(
            model_name=cfg.get("validation_model"),
        )
        self._answer_validator = AnswerValidator(
            use_llm=cfg.get("answer_validation_use_llm", False),
            model_name=cfg.get("answer_validation_model"),
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
        self._learner = learner if learner is not None else AgentLearner()
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
    def process(
        self,
        question: str,
        session_id: str,
        retriever_mode: Optional[str] = None,
        filename: Optional[str] = None,
        project_id: Optional[str] = None,
        user_id: Optional[str] = None,
        defer_request_completed: bool = False,
    ) -> PipelineContext:
        """
        Run the full pre-processing pipeline (Stages 1–7).
        Returns a PipelineContext ready to be passed into the LangGraph agent.

        Args:
            question: The user's query.
            session_id: Unique session identifier.
            retriever_mode: "vector" | "bm25" | "hybrid" | None (default).
            filename: If set, restrict retrieval to chunks from this document.
            project_id: If set, restrict retrieval to chunks from this project.
            user_id: If set, user context identifier.
            defer_request_completed: When True, skip emitting/publishing the
                final request_completed event here. The caller (API layer)
                records post-pipeline LLM usage on ctx.token_budget and calls
                finalize_trace() after the LangGraph agent finishes, so the
                single completion event carries the COMPLETE request cost.
        """
        ctx = PipelineContext(
            question=question,
            session_id=session_id,
            project_id=project_id,
            user_id=user_id,
            filename=filename,
        )
        trace = PipelineTrace(session_id=session_id, question=question)
        ctx.trace = trace

        # ── V3.5: Initialize AgentState ──────────────────────────────────────
        import uuid
        request_id = str(uuid.uuid4())
        ctx.agent_state = AgentState(
            request_id=request_id,
            question=question,
        )
        logger.info(
            "agent.request.started request_id=%s session_id=%s question=%r",
            request_id, session_id, question[:80],
        )

        # ── V4.6: Execution identity (StepContext lineage) ───────────────────
        # Distinct from request_id: identifies this execution run so every
        # propagated step output can be traced back to its origin.
        ctx.execution_id = str(uuid.uuid4())

        # ── V4.8: Event-based agent execution trace (passive) ────────────────
        # Correlates request/execution/session/project. Records lifecycle
        # decisions only — never prompts, outputs, or secrets.
        ctx.agent_trace = AgentTrace(
            request_id=request_id,
            execution_id=ctx.execution_id,
            session_id=session_id,
            project_id=project_id or "",
        )
        record_trace(ctx, "execution", "request_started")

        # ── V4.9: Token budgets (request + per-step) ────────────────────────
        # Caps are fixed per request; enforcement happens at the executor /
        # LLM call boundary — this stage only attaches the budget.
        ctx.token_budget = TokenBudget(
            request_budget_tokens=int(
                self._cfg.get("request_token_budget", DEFAULT_REQUEST_BUDGET_TOKENS)
            ),
            per_step_budget_tokens=int(
                self._cfg.get("step_token_budget", DEFAULT_STEP_BUDGET_TOKENS)
            ),
        )

        # ── V4.11: Reliability & Cancellation ─────────────────────────────
        # Timeout policy (tool / step / request) measured on an injectable
        # clock; the ledger prevents duplicate execution once an
        # (execution_id, step_id) pair has a terminal outcome.
        ctx.reliability = ReliabilityGuard(policy=TimeoutPolicy(
            tool_timeout_s=float(
                self._cfg.get("tool_timeout_s", DEFAULT_TOOL_TIMEOUT_S)
            ),
            step_timeout_s=float(
                self._cfg.get("step_timeout_s", DEFAULT_STEP_TIMEOUT_S)
            ),
            request_timeout_s=float(
                self._cfg.get("request_timeout_s", DEFAULT_REQUEST_TIMEOUT_S)
            ),
        ))
        ctx.idempotency = IdempotencyLedger()

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

        # ── V3.5: Populate intent in AgentState ──────────────────────────────
        if ctx.agent_state:
            ctx.agent_state.intent = ctx.intent.intent.value
            ctx.agent_state.intent_confidence = ctx.intent.confidence
            logger.debug(
                "agent.intent.classified request_id=%s intent=%s confidence=%.2f",
                ctx.agent_state.request_id, ctx.agent_state.intent,
                ctx.agent_state.intent_confidence or 0.0,
            )
            record_trace(
                ctx, "intent", "intent_classified",
                status=ctx.agent_state.intent,
                metadata={"confidence": ctx.intent.confidence,
                          "used_llm": bool(ctx.intent.used_llm)},
            )

        # ── Stage 2: Request Routing ─────────────────────────────────────────
        t2 = time.monotonic()
        ctx.route = self._router.route(ctx.intent)
        trace.route_decision = ctx.route.decision.value

        # ── V3.5: Populate route in AgentState ────────────────────────────────
        if ctx.agent_state:
            ctx.agent_state.route = ctx.route.decision.value
            logger.debug(
                "agent.route.selected request_id=%s route=%s",
                ctx.agent_state.request_id, ctx.agent_state.route,
            )
            record_trace(
                ctx, "routing", "route_selected",
                status=ctx.agent_state.route,
                metadata={"skip_retrieval": bool(getattr(ctx.route, "skip_retrieval", False))},
            )

        # ── Stage 2b: Planner (creates execution plan & source policy) ────────
        ctx.plan = self._planner.create_plan(question, ctx.intent, ctx.route)
        ctx.source_policy = self._planner.plan(ctx.intent, ctx.route)

        # ── V3.5: Populate plan metadata + step slots in AgentState ──────────
        if ctx.agent_state and ctx.plan:
            ctx.agent_state.goal = ctx.plan.goal
            ctx.agent_state.plan_steps = len(ctx.plan.steps)
            ctx.agent_state.steps = [
                StepExecutionState(
                    step_id=s.step_id,
                    tool=s.tool,
                    status="pending",
                )
                for s in ctx.plan.steps
            ]
            logger.debug(
                "agent.plan.created request_id=%s goal=%r steps=%d",
                ctx.agent_state.request_id, ctx.plan.goal, len(ctx.plan.steps),
            )
            record_trace(
                ctx, "planning", "plan_created",
                status="created",
                metadata={"steps": len(ctx.plan.steps),
                          "requires_tools": bool(ctx.plan.requires_tools)},
            )

        # ── Stage 2.5: Context Orchestrator (V3.6) ───────────────────────────
        ctx.context_request = self._context_orchestrator.build_request(question, ctx.intent, ctx.plan)
        ctx.context = self._context_orchestrator.retrieve(ctx.context_request, ctx)

        # ── V4.10: untrusted retrieved content boundary ─────────────────────
        # KB/web/document content is DATA, never instructions: secrets/PII
        # are redacted, instruction-like phrases neutralized, and the rest
        # wrapped in explicit untrusted-content delimiters. Every decision
        # is recorded on the existing AgentTrace (same V4.8 correlation IDs).
        ctx.context, content_findings = sanitize_retrieved_context(ctx.context)
        if content_findings:
            record_security(ctx, "flag", content_findings)
        ctx.context_text = ctx.context.to_prompt_context()

        # ── Stage 2b+: Capability Selection (V3.9) ───────────────────────────
        # Matches every plan step to an existing, registered, permitted
        # capability. Pure decision layer — never executes tools. Failures
        # are recorded per step and never break the request.
        try:
            ctx.capability_selections = self._selector.select(ctx.plan, context=ctx)
        except Exception as exc:
            logger.warning(
                "capability_selection_failed session_id=%s error_type=%s error=%s",
                session_id, type(exc).__name__, exc,
            )
        record_trace(
            ctx, "capability_selection", "capability_selected",
            status="selected",
            metadata={"selections": len(ctx.capability_selections or [])},
        )

        # ── Stage 2b+.2: Tool Selection (V3.11) ──────────────────────────────
        # Turns allowed capabilities into concrete registered tools + validated
        # arguments. Pure decision layer — never executes tools.
        try:
            ctx.tool_selections = self._tool_selector.select(
                ctx.plan,
                context=ctx,
                capability_selections=ctx.capability_selections,
            )
        except Exception as exc:
            logger.warning(
                "tool_selection_failed session_id=%s error_type=%s error=%s",
                session_id, type(exc).__name__, exc,
            )
        record_trace(
            ctx, "tool_selection", "tool_selected",
            status="selected",
            metadata={"selections": len(ctx.tool_selections or [])},
        )

        # ── Stage 2c': Agent Execution Loop (V3.12) ──────────────────────────
        # Bounded, deterministic: one eligible step per iteration through the
        # executor, always with the same authoritative V3.10/V3.11 selections.
        # A loop failure keeps the pipeline safe with a failed ExecutionResult.
        try:
            ctx.execution_loop = self._execution_loop.run(
                ctx.plan,
                context=ctx,
                capability_selections=ctx.capability_selections,
                tool_selections=ctx.tool_selections,
            )
            ctx.execution = (
                ctx.execution_loop.execution
                if ctx.execution_loop is not None
                else None
            )
        except Exception as exc:
            logger.warning(
                "execution_loop_failed session_id=%s error_type=%s error=%s",
                session_id, type(exc).__name__, exc,
            )
            ctx.execution = ExecutionResult(
                status="failed",
                step_results=[],
                outputs={},
                final_output=None,
                # Stable, capped: raw exception text never enters the trace
                # that is persisted to Redis (V4 review finding).
                error=f"execution loop failed: {type(exc).__name__}"[:500],
            )

        # ── V3.5: Finalize execution status in AgentState ────────────────────
        if ctx.agent_state:
            finalize_execution_status(ctx.agent_state)

        # ── Stage 2d: Synthesizer (combines step outputs into final answer) ───
        ctx.synthesis = self._synthesizer.synthesize(
            question, ctx.plan, ctx.execution, context=ctx
        )
        trace.source_policy = ctx.source_policy.policy.value
        trace.answer_mode = ctx.source_policy.policy.value
        trace.requires_evidence = ctx.source_policy.contract.requires_evidence
        trace.min_evidence = ctx.source_policy.contract.min_evidence

        # ── Stage 2e: Answer Validation & Grounding (V3.7) ───────────────────
        # Synthesis → Validation → FINAL ANSWER.
        # On validation failure the final answer becomes a safe clarification.
        # Never retries, never re-plans, never exposes internal errors.
        if ctx.synthesis is not None:
            validation_start = time.monotonic()
            ctx.validation = self._answer_validator.validate(
                question=question,
                answer=ctx.synthesis.answer,
                context=ctx.context,
                execution=ctx.execution,
            )
            if ctx.validation is not None:
                # validation_completed is emitted HERE on the pipeline
                # context: the validator itself receives ctx.context (the
                # retrieved-content boundary), which carries no agent_trace,
                # so its own record_trace calls resolve to a no-op. This
                # keeps the event on the request trace.
                record_trace(
                    ctx, "validation", "validation_completed",
                    status="valid" if ctx.validation.valid else "invalid",
                    duration_ms=round((time.monotonic() - validation_start) * 1000, 2),
                    metadata={
                        "grounded": bool(getattr(ctx.validation, "grounded", False)),
                        "issues": len(getattr(ctx.validation, "issues", []) or []),
                    },
                )
            if ctx.validation is not None and not ctx.validation.valid:
                logger.info(
                    "validation_rejected session_id=%s intent=%s issues=%s",
                    session_id,
                    ctx.intent_label,
                    ctx.validation.issues[:3],
                )
                ctx.synthesis.answer = SAFE_CLARIFICATION_MESSAGE

        # ── Stage 2f: Memory Learning (V3.8) ─────────────────────────────────
        # Runs immediately after validation, on the final answer only.
        # A failed validation produces no learning — nothing is learned from
        # a failed answer. Memory V2 failures are absorbed by the learner
        # and never affect the answer.
        if (
            ctx.synthesis is not None
            and self._cfg.get("learning_enabled", True)
        ):
            try:
                ctx.learning = self._learner.learn(
                    question=ctx.question,
                    answer=ctx.synthesis.answer,
                    intent=ctx.intent,
                    execution=ctx.execution,
                    validation=ctx.validation,
                    context=ctx,
                )
                if ctx.learning:
                    logger.info(
                        "pipeline_learning session_id=%s created=%d updated=%d skipped=%d reason=%r",
                        session_id,
                        ctx.learning.memories_created,
                        ctx.learning.memories_updated,
                        ctx.learning.memories_skipped,
                        ctx.learning.reason,
                    )
            except Exception as exc:
                logger.warning(
                    "pipeline_learning_failed session_id=%s error_type=%s error=%s",
                    session_id, type(exc).__name__, exc,
                )
                ctx.learning = LearningResult(
                    memories_skipped=0,
                    reason="learning aborted without affecting the answer",
                )

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
            if ctx.context and ctx.context.retrieved_chunks:
                ctx.retrieved_chunks = ctx.context.retrieved_chunks
                current_retriever = self._select_retriever(retriever_mode)
                retrieval_timings = {}
                t4 = time.monotonic()
            else:
                # Stage 4: Retrieval (mode-switchable: hybrid / vector / bm25)
                if filename:
                    # Document-scoped chat: vector-only, BM25 has no source filter
                    current_retriever = self._vector_retriever
                else:
                    current_retriever = self._select_retriever(retriever_mode)
                t4 = time.monotonic()
                ctx.retrieved_chunks, retrieval_timings = current_retriever.retrieve(
                    ctx.final_query, filename=filename, project_id=project_id
                )
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
                if ctx.context and ctx.context.ranked_chunks:
                    ctx.ranked_chunks = ctx.context.ranked_chunks
                    trace.reranker_ms = 0.0
                else:
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
        # ── V4.10: final LLM-bound context is sanitized the same way ────────
        # (covers the ranked-chunk path built outside the retrieved context).
        if ctx.context_text:
            cleaned_text, text_findings = sanitize_content(ctx.context_text)
            if text_findings:
                ctx.context_text = cleaned_text
                record_security(ctx, "flag", text_findings)
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

        # ── V4.8: Close the execution trace ─────────────────────────────────
        # V4.9: request-level cost totals attach to the SAME correlation IDs
        # (no new tracking mechanism).
        # When the API layer defers this call, the final request_completed is
        # emitted by finalize_trace() AFTER the LangGraph agent runs, so the
        # single completion event reflects the complete request cost.
        if not defer_request_completed:
            self.finalize_trace(ctx)
        return ctx

    # ── Post-pipeline Agent LLM cost capture + trace finalization ─────────
    # The production LangGraph agent (graph.py call_model) runs AFTER
    # process() returns, so its LLM usage is invisible at pipeline end. The
    # API layer feeds the agent usage back HERE, then closes the trace here
    # too — keeping one single, complete request_completed event per request.

    def record_agent_usage(
        self,
        ctx: PipelineContext,
        usage_metadata: Optional[dict] = None,
        *,
        fallback_model: str = "",
    ) -> None:
        """Record the LangGraph agent LLM call into the request TokenBudget.

        Reuses the existing V4.9 accounting (same TokenBudget instance the
        executor/synthesizer/validator already share). Pure accounting:
        missing, malformed, or non-dict usage is a no-op — it can never
        fail the answer or change the response.
        """
        try:
            budget = getattr(ctx, "token_budget", None)
            if budget is None or not isinstance(usage_metadata, dict):
                return
            t_in = (
                usage_metadata.get("input_tokens")
                or usage_metadata.get("prompt_tokens")
                or 0
            )
            t_out = (
                usage_metadata.get("completion_tokens")
                or usage_metadata.get("output_tokens")
                or 0
            )
            model = usage_metadata.get("model") or fallback_model or ""
            budget.record(model, int(t_in), int(t_out))
        except Exception as exc:
            logger.warning("agent_usage_record_failed error=%s", exc)

    def finalize_trace(
        self,
        ctx: PipelineContext,
        status: Optional[str] = None,
    ) -> None:
        """Emit request_completed with the FULL request cost, then publish.

        Idempotent: a completed trace is never completed twice (the API
        layer may finalize once and a later error path may retry with an
        explicit status). Status derivation mirrors process(); the optional
        override exists for failed/partial flows. Never raises.

        The SAME finalization facts feed the trace event and the agent
        request metrics (Phase 3.2): one status (contract map_status plus
        the validation-failure downgrade) and one TokenBudget total — the
        metrics can never disagree with the trace they accompany.
        """
        try:
            tr = getattr(ctx, "agent_trace", None)
            if tr is None:
                return
            if any(e.event == "request_completed" for e in tr.events()):
                logger.debug("trace_already_completed request_id=%s", tr.request_id)
                return
            exec_status = status or map_status(ctx)
            if ctx.validation is not None and not ctx.validation.valid:
                exec_status = "failed"
            budget_meta: dict = {}
            if ctx.token_budget is not None:
                budget_meta = {
                    "estimated_cost_usd": round(ctx.token_budget.total_cost_usd(), 6),
                    "models": ",".join(ctx.token_budget.models_used()) or "none",
                }
            duration_ms = round((time.monotonic() - ctx._start_time) * 1000, 2)
            record_trace(
                ctx, "execution", "request_completed",
                status=exec_status,
                duration_ms=duration_ms,
                metadata=budget_meta or None,
            )
            # ── Agent request metrics (Phase 3.2) ──────────────────────────
            # Recorded ONLY here, from the same status and the same shared
            # TokenBudget that produced the trace event above — a single
            # accounting path for trace, contract, and Prometheus.
            core_metrics.safe_agent_count("requests_total", status=exec_status)
            core_metrics.safe_agent_observe(
                "request_duration_seconds", duration_ms / 1000.0
            )
            try:
                usage = (
                    ctx.token_budget.usage_by_model()
                    if ctx.token_budget is not None
                    else None
                )
                for model, v in sorted((usage or {}).items()):
                    tokens = int(v.get("input_tokens", 0) or 0) + int(
                        v.get("output_tokens", 0) or 0
                    )
                    cost = float(v.get("cost_usd", 0.0) or 0.0)
                    if tokens:
                        core_metrics.safe_agent_count(
                            "request_tokens_total", amount=tokens, model=model
                        )
                    if cost:
                        core_metrics.safe_agent_count(
                            "request_cost_usd_total", amount=cost, model=model
                        )
            except Exception as exc:
                logger.warning("agent_request_metrics_failed error=%s", exc)
            tr.publish(LoggingTraceObserver())
        except Exception as exc:
            logger.warning("trace_finalize_failed error=%s", exc)

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

    @staticmethod
    def kb_not_covered_message() -> str:
        return _KB_NOT_COVERED_MESSAGE
