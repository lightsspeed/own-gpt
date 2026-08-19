"""Capability Registry — makes the platform self-describing.

Each capability advertises its owner, dependencies, lifecycle stage, maturity,
artifacts, and API surface. Enables documentation generators, operator UIs,
and system health reports to introspect the platform without hardcoding.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class MaturityLevel(str, Enum):
    PLANNED = "planned"           # Not yet implemented
    IMPLEMENTED = "implemented"   # Exists but may lack operational maturity
    MATURE = "mature"             # Stable, tested, monitored
    ADAPTIVE = "adaptive"         # Self-improving via the platform itself


@dataclass(frozen=True)
class Capability:
    """Declaration of a platform capability."""
    id: str
    name: str
    description: str
    owner: str                          # package or module name
    dependencies: tuple[str, ...] = ()  # capability IDs this depends on
    lifecycle_stage: str = ""           # observe/measure/explain/propose/validate/apply/operate
    maturity: MaturityLevel = MaturityLevel.IMPLEMENTED
    artifacts: tuple[str, ...] = ()
    api_prefix: str = ""


# ── Registry ──────────────────────────────────────────────────────────

CAPABILITIES: dict[str, Capability] = {}


def register(cap: Capability) -> Capability:
    CAPABILITIES[cap.id] = cap
    return cap


def get(cap_id: str) -> Optional[Capability]:
    return CAPABILITIES.get(cap_id)


def list_by_owner(owner: str) -> list[Capability]:
    return [c for c in CAPABILITIES.values() if c.owner == owner]


def list_by_stage(stage: str) -> list[Capability]:
    return [c for c in CAPABILITIES.values() if c.lifecycle_stage == stage]


def list_all() -> list[Capability]:
    return list(CAPABILITIES.values())


def to_dict() -> dict:
    return {
        "count": len(CAPABILITIES),
        "capabilities": {
            c.id: {
                "name": c.name,
                "owner": c.owner,
                "dependencies": list(c.dependencies),
                "lifecycle_stage": c.lifecycle_stage,
                "maturity": c.maturity.value,
                "artifacts": list(c.artifacts),
                "api_prefix": c.api_prefix,
            }
            for c in sorted(CAPABILITIES.values(), key=lambda x: x.id)
        },
    }


# ── Register all platform capabilities ─────────────────────────────────

# Runtime
register(Capability(
    id="intent_classification", name="Intent Classification",
    description="Classifies user queries into intents (knowledge, coding, web, etc.) using rules + LLM",
    owner="agent.pipeline", lifecycle_stage="observe",
    maturity=MaturityLevel.MATURE,
    artifacts=("IntentResult",), api_prefix="/api/v1/chat",
))

register(Capability(
    id="hybrid_retrieval", name="Hybrid Retrieval",
    description="Multi-strategy retrieval combining vector search, BM25, RRF fusion, and reranking",
    owner="agent.pipeline", lifecycle_stage="observe",
    maturity=MaturityLevel.MATURE,
    dependencies=("intent_classification",),
    artifacts=("RetrievalResult",),
))

register(Capability(
    id="answer_generation", name="Answer Generation",
    description="Generates answers with citations using retrieved context and LLM",
    owner="agent.pipeline", lifecycle_stage="observe",
    maturity=MaturityLevel.MATURE,
    dependencies=("hybrid_retrieval",),
    artifacts=("GenerationResult",),
))

# Evaluation
register(Capability(
    id="evaluation_pipeline", name="Evaluation Pipeline",
    description="Evaluates answer confidence, faithfulness, context precision and recall",
    owner="evaluation", lifecycle_stage="measure",
    maturity=MaturityLevel.MATURE,
    dependencies=("answer_generation",),
    artifacts=("LearningRecord",),
))

register(Capability(
    id="benchmark_runner", name="Benchmark Runner",
    description="Executes IntentAccuracy and other benchmark datasets for regression detection against stored baselines",
    owner="evaluation", lifecycle_stage="measure",
    maturity=MaturityLevel.MATURE,
    artifacts=("BenchmarkReport", "BenchmarkBaseline"),
))

# Learning
register(Capability(
    id="learning_ledger", name="Learning Ledger",
    description="Persists every production query as a LearningRecord with full lifecycle telemetry",
    owner="learning", lifecycle_stage="observe",
    maturity=MaturityLevel.MATURE,
    dependencies=("evaluation_pipeline",),
    artifacts=("LearningRecord", "UserEvent"),
))

register(Capability(
    id="replay", name="Replay",
    description="Replays historical LearningRecords for offline analysis and experiment baselines",
    owner="learning", lifecycle_stage="measure",
    maturity=MaturityLevel.MATURE,
    dependencies=("learning_ledger",),
    artifacts=("ReplayResult",),
))

register(Capability(
    id="telemetry_collection", name="Telemetry Collection",
    description="Captures user interactions (thumbs, copies, regenerations) as UserEvents",
    owner="learning.telemetry", lifecycle_stage="observe",
    maturity=MaturityLevel.MATURE,
    dependencies=("learning_ledger",),
    artifacts=("UserEvent",), api_prefix="/api/v1/telemetry",
))

# Analytics
register(Capability(
    id="query_analytics", name="Query Analytics",
    description="Analyzes query patterns: top questions, failures, knowledge gaps, copy/regenerate rates",
    owner="learning.analytics", lifecycle_stage="measure",
    maturity=MaturityLevel.MATURE,
    dependencies=("learning_ledger",),
    artifacts=("QueryIntelligenceReport",),
))

register(Capability(
    id="retrieval_analytics", name="Retrieval Analytics",
    description="Per-document and per-chunk effectiveness metrics with quality tier classification",
    owner="learning.analytics", lifecycle_stage="measure",
    maturity=MaturityLevel.MATURE,
    dependencies=("learning_ledger",),
    artifacts=("RetrievalIntelligenceReport",),
))

register(Capability(
    id="routing_analytics", name="Routing Analytics",
    description="Intent distribution, rule vs LLM classification rate, confidence by intent",
    owner="learning.analytics", lifecycle_stage="measure",
    maturity=MaturityLevel.MATURE,
    dependencies=("intent_classification", "learning_ledger"),
    artifacts=("RoutingAnalyticsReport",),
))

register(Capability(
    id="behavior_analytics", name="Behavior Analytics",
    description="User behavior metrics: thumb rates, copy rates, regenerate rates by intent",
    owner="learning.analytics", lifecycle_stage="measure",
    maturity=MaturityLevel.MATURE,
    dependencies=("telemetry_collection",),
    artifacts=("UserBehaviorReport",),
))

register(Capability(
    id="trend_analytics", name="Trend Analytics",
    description="Time-series analysis: daily/weekly volume, confidence trends, growth rates",
    owner="learning.analytics", lifecycle_stage="measure",
    maturity=MaturityLevel.MATURE,
    dependencies=("learning_ledger",),
    artifacts=("TrendAnalyticsReport",),
))

# Evidence
register(Capability(
    id="evidence_engine", name="Evidence Engine",
    description="Explains why findings occurred with root cause analysis, evidence strength scoring, and recommendations",
    owner="learning.evidence", lifecycle_stage="explain",
    maturity=MaturityLevel.MATURE,
    dependencies=("query_analytics", "retrieval_analytics", "routing_analytics"),
    artifacts=("Finding", "Evidence", "EvidenceReport"), api_prefix="/api/v1/evidence",
))

register(Capability(
    id="confidence_calibration", name="Confidence Calibration",
    description="Measures reliability of confidence scores via ECE, buckets, and over/underconfidence detection",
    owner="learning.evidence", lifecycle_stage="explain",
    maturity=MaturityLevel.IMPLEMENTED,
    dependencies=("learning_ledger",),
    artifacts=("CalibrationReport",),
))

register(Capability(
    id="failure_tree", name="Retrieval Failure Tree",
    description="Classifies every failed query into a failure mode: no docs, low reranker, routing issue, etc.",
    owner="learning.evidence", lifecycle_stage="explain",
    maturity=MaturityLevel.IMPLEMENTED,
    dependencies=("learning_ledger",),
    artifacts=("FailureTreeReport",),
))

# Recommendations
register(Capability(
    id="recommendation_generation", name="Recommendation Generation",
    description="Formats Evidence Engine Findings into structured Recommendation objects for human review",
    owner="learning.analytics", lifecycle_stage="propose",
    maturity=MaturityLevel.MATURE,
    dependencies=("evidence_engine",),
    artifacts=("Recommendation", "KnowledgeGap", "WeakChunk", "DeadChunk"),
))

# Experiments
register(Capability(
    id="experimentation", name="Experimentation Framework",
    description="Offline experiment definition, replay execution, metric comparison, and decision candidate generation",
    owner="learning.experiments", lifecycle_stage="validate",
    maturity=MaturityLevel.IMPLEMENTED,
    dependencies=("replay", "recommendation_generation"),
    artifacts=("ExperimentDefinition", "ExperimentResult", "DecisionCandidate"),
    api_prefix="/api/v1/experiments",
))

register(Capability(
    id="experiment_checkout", name="Experiment Checkout Lane (V3.13-3.15)",
    description="Single-use AuthorizationCode artifacts gate experiment execution: operator approval bound to experiment_id, idempotent exchange, revocation, and a fail-closed sandbox boundary that never bypasses existing capability or tool gates; every outcome is recorded as an immutable ExecutionResult with an append-only audit trail, and read-only query endpoints expose results and audit history per experiment with secrets redacted (404 on unknown)",
    owner="learning.experiments", lifecycle_stage="validate",
    maturity=MaturityLevel.IMPLEMENTED,
    dependencies=("experimentation",),
    artifacts=("AuthorizationCode", "AuthorizationEvent", "ExperimentResult"),
    api_prefix="/api/v1/experiments",
))

# Runtime tooling
register(Capability(
    id="tool_sandboxing", name="Tool Sandboxing & HITL Gate",
    description="Guardrails classify tool calls; mutating tools require human approval and execute in a sandboxed subprocess with timeout and memory caps",
    owner="agent.pipeline", lifecycle_stage="apply",
    maturity=MaturityLevel.IMPLEMENTED,
    dependencies=("operations_control_plane",),
    artifacts=("ToolExecution", "GuardrailDecision"), api_prefix="/api/v1/operations/tool-executions",
))

# Governance
register(Capability(
    id="architecture_governance", name="Architecture Governance",
    description="Importable principles, lifecycle stages, artifact types, and validation guardrails",
    owner="learning.architecture", lifecycle_stage="apply",
    maturity=MaturityLevel.MATURE,
    artifacts=("Principle", "ArtifactType", "Lineage", "EvidencePolicy"),
))

# Configuration
register(Capability(
    id="config_management", name="Configuration Management",
    description="Immutable configuration snapshots, pointer-based rollback, parameter diffs",
    owner="learning.config", lifecycle_stage="apply",
    maturity=MaturityLevel.IMPLEMENTED,
    dependencies=("architecture_governance",),
    artifacts=("ConfigurationSnapshot", "ConfigDiff"), api_prefix="/api/v1/config",
))

# Operations
register(Capability(
    id="operations_control_plane", name="Operations Control Plane",
    description="Aggregation endpoints for five workspaces: Findings, Recommendations, Experiments, Decisions, Configurations",
    owner="learning.operations", lifecycle_stage="operate",
    maturity=MaturityLevel.IMPLEMENTED,
    dependencies=("evidence_engine", "recommendation_generation", "experimentation", "config_management", "decision_lifecycle"),
    api_prefix="/api/v1/operations",
))

register(Capability(
    id="decision_lifecycle", name="Decision Lifecycle",
    description="Human review of recommendations (approve/dismiss) with immutable Decision artifacts, and apply-to-configuration materialization",
    owner="learning.operations", lifecycle_stage="apply",
    maturity=MaturityLevel.IMPLEMENTED,
    dependencies=("recommendation_generation", "config_management"),
    artifacts=("ReviewRecord", "Decision"), api_prefix="/api/v1/operations/recommendations",
))

register(Capability(
    id="artifact_explorer", name="Artifact Explorer",
    description="Full lineage traversal from any artifact ID through the entire platform chain",
    owner="learning.operations", lifecycle_stage="operate",
    maturity=MaturityLevel.IMPLEMENTED,
    dependencies=("architecture_governance",),
    api_prefix="/api/v1/operations/explore",
))

register(Capability(
    id="agent_memory", name="Agent Semantic Memory",
    description="Immutable, scoped memory facts (global/conversation) with dedupe, lifecycle events, and operator-governed forgetting",
    owner="learning.operations", lifecycle_stage="operate",
    maturity=MaturityLevel.IMPLEMENTED,
    dependencies=("architecture_governance", "tool_sandboxing"),
    artifacts=("MemoryFact",), api_prefix="/api/v1/operations/memories",
))

register(Capability(
    id="episodic_memory", name="Episodic Conversation Memory",
    description="Cross-session recall: past conversations consolidated into durable summary artifacts (lazy, capped) and retrieved by cosine similarity for memory-intent queries in new sessions",
    owner="learning.operations", lifecycle_stage="operate",
    maturity=MaturityLevel.IMPLEMENTED,
    dependencies=("agent_memory",),
    artifacts=("SessionSummary",), api_prefix="",
))

register(Capability(
    id="memory_v2", name="Memory V2 — Governed Memory Store",
    description="Durable, scoped, curated memories with authority-aware conflict resolution, lifecycle events, and vector retrieval; backs the agent recall node (retrieve_memory) and the memory tools",
    owner="services.memory", lifecycle_stage="operate",
    maturity=MaturityLevel.IMPLEMENTED,
    dependencies=("architecture_governance", "agent_memory"),
    artifacts=("MemoryEntity", "MemoryEvent"),
    api_prefix="/api/v1/memory",
))

register(Capability(
    id="memory_extraction", name="Memory Extraction",
    description="Detached three-gate extraction of durable user facts from completed conversations into the governed memory store (pending status, extracted authority — never self-approved)",
    owner="learning.extraction", lifecycle_stage="observe",
    maturity=MaturityLevel.IMPLEMENTED,
    dependencies=("memory_v2",),
    artifacts=("MemoryEntity",),
))

register(Capability(
    id="pipeline_learning", name="Pipeline Memory Learning (V3.8)",
    description="In-pipeline learning stage that persists explicit, durable user statements (preferences, facts, corrections) through Memory V2 after validation; runs only on validated answers and never executes tools",
    owner="agent.pipeline", lifecycle_stage="operate",
    maturity=MaturityLevel.IMPLEMENTED,
    dependencies=("memory_v2",),
    artifacts=("LearningResult", "MemoryEntity"),
))

register(Capability(
    id="capability_matching", name="Capability Selection & Tool Matching (V3.9)",
    description="Deterministic pre-execution stage that matches PlanSteps to existing registered capabilities and tools, verifies the Capability Registry, tool registration, source policy, and configuration-driven availability — never executes tools",
    owner="agent.pipeline", lifecycle_stage="apply",
    maturity=MaturityLevel.IMPLEMENTED,
    dependencies=("tool_sandboxing", "architecture_governance"),
    artifacts=("CapabilitySelection",),
))

register(Capability(
    id="tool_selection", name="Tool Selection & Argument Construction (V3.11)",
    description="Deterministic pre-execution stage that turns allowed capability selections into concrete registered tool + validated arguments (query, project_id, fact, user/session scope) — never executes tools",
    owner="agent.pipeline", lifecycle_stage="apply",
    maturity=MaturityLevel.IMPLEMENTED,
    dependencies=("capability_matching", "tool_sandboxing"),
    artifacts=("ToolSelection",),
))

register(Capability(
    id="execution_loop", name="Controlled Agent Execution Loop (V3.12)",
    description="Bounded deterministic loop that executes one eligible plan step per iteration through the executor, never bypassing capability or tool selection; hard caps on steps and iterations, no retries or replanning",
    owner="agent.pipeline", lifecycle_stage="apply",
    maturity=MaturityLevel.IMPLEMENTED,
    dependencies=("capability_matching", "tool_selection"),
    artifacts=("LoopResult", "ExecutionResult"),
))

register(Capability(
    id="step_context", name="Step Context & Execution Continuity (V4.6)",
    description="Structured dependency-scoped context for plan steps: a step receives ONLY outputs of its declared dependencies, size-bounded with safe truncation; every propagated entry retains originating step_id + execution_id for synthesis and audit; reuses Memory V2 and AgentState, introduces no new memory system",
    owner="agent.pipeline", lifecycle_stage="apply",
    maturity=MaturityLevel.IMPLEMENTED,
    dependencies=("execution_loop",),
    artifacts=("StepContext", "ContextEntry"),
))

register(Capability(
    id="tool_result_standard", name="Tool Result Standardization (V4.7)",
    description="Standard boundary for every tool outcome: ToolResult with status completed|failed|blocked|empty|timeout and stable error codes (TOOL_FAILED, TOOL_BLOCKED, TOOL_EMPTY, TOOL_TIMEOUT, PROVIDER_UNAVAILABLE, INVALID_TOOL_ARGUMENTS, AUTHORIZATION_REQUIRED); existing tool implementations untouched, normalization at the boundary only; no raw provider text as primary client error",
    owner="agent.pipeline", lifecycle_stage="apply",
    maturity=MaturityLevel.IMPLEMENTED,
    dependencies=("step_context", "tool_selection"),
    artifacts=("ToolResult",),
))

register(Capability(
    id="agent_tracing", name="Agent Execution Observability (V4.8)",
    description="Passive event-based AgentTrace over the execution lifecycle (intent, routing, planning, capability_selection, tool_selection, execution, synthesis, validation, learning); reuses existing logging + TracingService — no new telemetry system; secrets, prompts, memory contents, and raw tool outputs never recorded; derived metrics exposed for the existing observability stack",
    owner="agent.pipeline", lifecycle_stage="operate",
    maturity=MaturityLevel.IMPLEMENTED,
    dependencies=("tool_result_standard",),
    artifacts=("AgentTrace", "TraceEvent"),
))

register(Capability(
    id="token_governance", name="Cost & Token Governance (V4.9)",
    description="Per-request and per-step token accounting with provider/model-aware estimated cost and budget enforcement BEFORE LLM calls; blocks further steps when request or step budgets are exhausted (runaway multi-step prevention) and gates optional synthesis/validation escalation; cost data attaches to the existing AgentTrace correlation IDs — no new billing or telemetry system",
    owner="agent.pipeline", lifecycle_stage="operate",
    maturity=MaturityLevel.IMPLEMENTED,
    dependencies=("agent_tracing", "tool_result_standard"),
    artifacts=("TokenBudget", "TokenUsage"),
))

register(Capability(
    id="agent_security_boundary", name="Agent Security Boundary (V4.10)",
    description="One boundary where untrusted material enters the agent: tool input validation (scalar-only, secret/PII redaction), tool output sanitization, and retrieved-content containment (prompt-injection phrase neutralization + untrusted-content wrapping); complements existing authorization layers (guardrail, tool_gate, V3.10/V3.11 selections) without duplicating them; every security decision recorded on the existing AgentTrace — no new security or telemetry system",
    owner="agent.pipeline", lifecycle_stage="apply",
    maturity=MaturityLevel.IMPLEMENTED,
    dependencies=("agent_tracing", "tool_result_standard", "tool_selection"),
    artifacts=("SecurityFinding",),
))

register(Capability(
    id="production_reliability", name="Production Reliability & Cancellation (V4.11)",
    description="Timeout boundaries at three levels (per-tool, per-step, request-level) re-labeled onto the existing TOOL_TIMEOUT taxonomy — no new error vocabulary; cooperative cancellation propagating request to execution to current step with nothing left running or pending; partial execution recovery (completed steps stay valid, dependants blocked, independent steps continue once — no automatic retry, no replanning); idempotent execution where the first terminal (execution_id, step_id) outcome wins; all gates order AFTER capability/tool selection and never bypass the security boundary or token budget",
    owner="agent.pipeline", lifecycle_stage="operate",
    maturity=MaturityLevel.IMPLEMENTED,
    dependencies=("agent_tracing", "tool_result_standard", "token_governance"),
    artifacts=("ReliabilityGuard", "TimeoutPolicy", "IdempotencyLedger"),
))

register(Capability(
    id="agent_api_contract", name="Stable Agent API Contract (V4.12)",
    description="Pure DTO layer (AgentRequest/AgentResponse/AgentError/StreamEvent/ExecutionSummary/ModelUsageSummary) with one deterministic status mapping (completed/partial/failed/blocked/cancelled/timed_out), enumerated SSE payload projection, stable error mapping that never leaks internal text, and backwards-compatible legacy chat keys; the production chat API keeps its stable SSE vocabulary unchanged",
    owner="agent.contract", lifecycle_stage="operate",
    maturity=MaturityLevel.IMPLEMENTED,
    dependencies=("agent_tracing", "token_governance", "production_reliability"),
    artifacts=("AgentRequest", "AgentResponse", "AgentError", "StreamEvent",
               "ExecutionSummary", "ModelUsageSummary"),
    api_prefix="/api/v1/chat",
))

register(Capability(
    id="agent_execution_metrics", name="Agent Execution Metrics (Phase 3.2)",
    description="Bounded-label Prometheus families (owngpt_agent_*) recorded at the two authoritative boundaries: request status/duration/tokens/cost at the single finalization boundary (finalize_trace — same status and same TokenBudget totals as the request_completed trace event) and tool calls/duration/failures/blocks at the single guarded tool gate; failures and block reasons are finite taxonomies, model/tool collapse to allowlists plus 'other', and Prometheus/Grafana consume the same registry the /metrics endpoint already serves",
    owner="core.metrics", lifecycle_stage="operate",
    maturity=MaturityLevel.IMPLEMENTED,
    dependencies=("agent_api_contract", "agent_tracing", "token_governance",
                  "production_reliability"),
    artifacts=(
        "owngpt_agent_requests_total",
        "owngpt_agent_request_tokens_total",
        "owngpt_agent_request_cost_usd_total",
        "owngpt_agent_request_duration_seconds",
        "owngpt_agent_tool_calls_total",
        "owngpt_agent_tool_duration_seconds",
        "owngpt_agent_tool_failures_total",
        "owngpt_agent_tool_blocked_total",
    ),
    api_prefix="/metrics",
))

# Automation
register(Capability(
    id="continuous_evaluation", name="Continuous Evaluation",
    description="Scheduled execution of analytics + evidence pipeline with snapshot diffing and trigger detection",
    owner="learning.automation", lifecycle_stage="operate",
    maturity=MaturityLevel.IMPLEMENTED,
    dependencies=("evidence_engine", "config_management"),
    artifacts=("EvaluationSnapshot", "AutomationRun", "DailyBrief"),
    api_prefix="/api/v1/automation",
))

register(Capability(
    id="health_scoring", name="Health Scoring",
    description="Per-domain health scores (0-100) from Findings: Retrieval, Knowledge, Calibration, Routing, Experiments",
    owner="learning.automation", lifecycle_stage="operate",
    maturity=MaturityLevel.IMPLEMENTED,
    dependencies=("evidence_engine",),
    artifacts=("HealthDomainScore",),
    api_prefix="/api/v1/automation/health",
))

register(Capability(
    id="trigger_engine", name="Trigger Engine",
    description="State-change-driven alerts: confidence drops, ECE increases, finding surges, benchmark regressions",
    owner="learning.automation", lifecycle_stage="operate",
    maturity=MaturityLevel.IMPLEMENTED,
    dependencies=("continuous_evaluation",),
    artifacts=("Trigger",),
    api_prefix="/api/v1/automation/triggers",
))

register(Capability(
    id="daily_briefs", name="Daily Briefs",
    description="Concise operator-facing daily reports synthesizing health, findings, triggers, and recommendations",
    owner="learning.automation", lifecycle_stage="operate",
    maturity=MaturityLevel.IMPLEMENTED,
    dependencies=("continuous_evaluation", "health_scoring", "trigger_engine"),
    artifacts=("DailyBrief",),
    api_prefix="/api/v1/automation/brief",
))
