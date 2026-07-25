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
    description="Executes IntentAccuracy and other benchmark datasets for regression detection",
    owner="evaluation", lifecycle_stage="measure",
    maturity=MaturityLevel.MATURE,
    artifacts=("BenchmarkReport",),
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
    dependencies=("evidence_engine", "recommendation_generation", "experimentation", "config_management"),
    api_prefix="/api/v1/operations",
))

register(Capability(
    id="artifact_explorer", name="Artifact Explorer",
    description="Full lineage traversal from any artifact ID through the entire platform chain",
    owner="learning.operations", lifecycle_stage="operate",
    maturity=MaturityLevel.IMPLEMENTED,
    dependencies=("architecture_governance",),
    api_prefix="/api/v1/operations/explore",
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
