"""
Canonical data models for the Learning Ledger.

LearningRecord captures the complete lifecycle of a single query:
  query → intent → retrieval → generation → evaluation → user outcome

UserEvent captures individual user interactions tied back to a record.

Recommendation defines a suggested improvement surfaced by analytics.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from .architecture.artifacts import ArtifactType, Lineage


LEARNING_SCHEMA_VERSION = 1


class RecommendationType(str, Enum):
    KNOWLEDGE_GAP = "knowledge_gap"
    WEAK_CHUNK = "weak_chunk"
    DEAD_CHUNK = "dead_chunk"
    PROMPT_ISSUE = "prompt_issue"
    ROUTING_ISSUE = "routing_issue"
    EMBEDDING_ISSUE = "embedding_issue"
    BENCHMARK_CANDIDATE = "benchmark_candidate"


class RecommendationSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RecommendationStatus(str, Enum):
    OPEN = "open"
    APPROVED = "approved"
    DISMISSED = "dismissed"
    IMPLEMENTED = "implemented"


@dataclass
class LearningRecord:
    # ── Schema version (increment when adding breaking field changes) ──────
    learning_schema_version: int = LEARNING_SCHEMA_VERSION

    # ── Metadata ──────────────────────────────────────────────────────────
    record_id: str = ""
    timestamp: str = ""
    session_id: str = ""
    message_id: str = ""

    # ── Query ─────────────────────────────────────────────────────────────
    question: str = ""
    normalized_question: str = ""
    question_hash: str = ""
    intent: str = ""
    matched_rule: str = ""
    intent_confidence: float = 0.0

    # ── Retrieval ─────────────────────────────────────────────────────────
    retriever: str = ""
    answer_mode: str = ""
    documents: list[dict] = field(default_factory=list)
    chunks: list[dict] = field(default_factory=list)
    vector_scores: list[float] = field(default_factory=list)
    bm25_scores: list[float] = field(default_factory=list)
    rrf_scores: list[float] = field(default_factory=list)
    reranker_scores: list[float] = field(default_factory=list)

    # ── Generation ────────────────────────────────────────────────────────
    model: str = ""
    prompt_version: str = ""
    latency_ms: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0

    # ── Evaluation ────────────────────────────────────────────────────────
    confidence: float = 0.0
    faithfulness: Optional[float] = None
    context_precision: Optional[float] = None
    context_recall: Optional[float] = None
    hallucination_risk: Optional[str] = None

    # ── User ──────────────────────────────────────────────────────────────
    thumb: Optional[str] = None
    copied: bool = False
    regenerated: bool = False
    edited: bool = False
    follow_up: Optional[str] = None

    # ── Outcome ───────────────────────────────────────────────────────────
    accepted: bool = True
    resolved: bool = True
    failure_reason: Optional[str] = None

    # ── Version metadata ─────────────────────────────────────────────────
    pipeline_version: str = ""
    prompt_version_id: str = ""
    embedding_model: str = ""
    reranker_model: str = ""
    chunk_size: int = 0
    git_commit: str = ""
    dataset_hash: str = ""

    # Store-only fields (not part of the dataclass constructor logic)
    _extra: dict = field(default_factory=dict)

    _FIELDS = frozenset({
        "learning_schema_version", "record_id", "timestamp", "session_id", "message_id",
        "question", "normalized_question", "question_hash", "intent", "matched_rule", "intent_confidence",
        "retriever", "answer_mode", "documents", "chunks",
        "vector_scores", "bm25_scores", "rrf_scores", "reranker_scores",
        "model", "prompt_version", "latency_ms", "tokens_in", "tokens_out",
        "confidence", "faithfulness", "context_precision", "context_recall",
        "hallucination_risk", "thumb", "copied", "regenerated", "edited",
        "follow_up", "accepted", "resolved", "failure_reason",
        "pipeline_version", "prompt_version_id", "embedding_model",
        "reranker_model", "chunk_size", "git_commit", "dataset_hash",
    })

    def __post_init__(self):
        if not self.record_id:
            self.record_id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if not self.question_hash and self.normalized_question:
            self.question_hash = hashlib.sha256(
                self.normalized_question.encode("utf-8")
            ).hexdigest()[:16]

    def to_dict(self) -> dict:
        result = {}
        for k, v in self.__dict__.items():
            if k == "_extra":
                continue
            if isinstance(v, list):
                import json
                result[k] = json.dumps(v)
            else:
                result[k] = v
        return result

    @classmethod
    def from_dict(cls, d: dict) -> LearningRecord:
        import json
        kwargs = {}
        for k, v in d.items():
            if k not in cls._FIELDS:
                continue
            if k in ("documents", "chunks", "vector_scores", "bm25_scores",
                     "rrf_scores", "reranker_scores"):
                kwargs[k] = json.loads(v) if isinstance(v, str) else v
            elif k in ("copied", "regenerated", "edited", "accepted", "resolved"):
                kwargs[k] = bool(v)
            else:
                kwargs[k] = v
        return cls(**kwargs)


@dataclass
class UserEvent:
    event_id: str = ""
    record_id: str = ""
    session_id: str = ""
    type: str = ""
    metadata: dict = field(default_factory=dict)
    created_at: str = ""

    SUPPORTED_TYPES = frozenset({
        "thumb_up", "thumb_down",
        "copy", "regenerate", "retry",
        "rename", "share", "bookmark",
        "open_reference", "feedback",
    })

    def __post_init__(self):
        if not self.event_id:
            self.event_id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


@dataclass
class Recommendation:
    """
    A suggested improvement surfaced by analytics.
    Generated by the recommendation engine, never executed automatically.
    """
    id: str = ""
    type: RecommendationType = RecommendationType.KNOWLEDGE_GAP
    severity: RecommendationSeverity = RecommendationSeverity.MEDIUM
    confidence: float = 0.0
    title: str = ""
    description: str = ""
    evidence: dict = field(default_factory=dict)
    status: RecommendationStatus = RecommendationStatus.OPEN
    created_at: str = ""
    source_record_ids: list[str] = field(default_factory=list)
    finding_id: Optional[str] = None
    lineage: Optional[Lineage] = None

    def __post_init__(self):
        if not self.id:
            self.id = f"rec-{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if self.lineage is None:
            self.lineage = Lineage(
                artifact_id=self.id,
                parent_artifact_id=self.finding_id,
                parent_type=ArtifactType.FINDING,
            )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value if isinstance(self.type, Enum) else self.type,
            "severity": self.severity.value if isinstance(self.severity, Enum) else self.severity,
            "confidence": self.confidence,
            "title": self.title,
            "description": self.description,
            "evidence": self.evidence,
            "status": self.status.value if isinstance(self.status, Enum) else self.status,
            "created_at": self.created_at,
            "source_record_ids": self.source_record_ids,
            "finding_id": self.finding_id,
            "lineage": self.lineage.to_dict() if self.lineage else None,
        }


# ── Concrete Recommendation subtypes ──────────────────────────────────────


@dataclass
class KnowledgeGap(Recommendation):
    """A topic users ask about that the KB handles poorly or not at all."""
    topic: str = ""
    frequency: int = 1
    avg_confidence: float = 0.0

    def __post_init__(self):
        super().__post_init__()
        self.type = RecommendationType.KNOWLEDGE_GAP
        sev = RecommendationSeverity.CRITICAL if self.frequency >= 10 else (
            RecommendationSeverity.HIGH if self.frequency >= 5 else RecommendationSeverity.MEDIUM
        )
        self.severity = sev
        self.title = f"Knowledge Gap: \"{self.topic[:60]}\""
        self.description = (
            f"Repeated {self.frequency}x, avg confidence {self.avg_confidence:.2f}. "
            f"Users expect this knowledge but retrieval isn't satisfying."
        )


@dataclass
class WeakChunk(Recommendation):
    """A chunk that is retrieved often but rarely helps (low accept rate)."""
    chunk_id: str = ""
    source: str = ""
    retrieved_count: int = 1
    accept_rate: float = 0.0

    def __post_init__(self):
        super().__post_init__()
        self.type = RecommendationType.WEAK_CHUNK
        self.severity = RecommendationSeverity.MEDIUM
        self.title = f"Weak Chunk: {self.chunk_id[:60]}"
        self.description = (
            f"Retrieved {self.retrieved_count}x, accepted only {self.accept_rate:.0%}. "
            f"Consider revising or replacing this chunk."
        )


@dataclass
class DeadChunk(Recommendation):
    """A chunk that is retrieved frequently but almost never accepted."""
    chunk_id: str = ""
    source: str = ""
    retrieved_count: int = 1
    accept_rate: float = 0.0

    def __post_init__(self):
        super().__post_init__()
        self.type = RecommendationType.DEAD_CHUNK
        self.severity = RecommendationSeverity.HIGH
        self.title = f"Dead Chunk: {self.chunk_id[:60]}"
        self.description = (
            f"Retrieved {self.retrieved_count}x, accepted only {self.accept_rate:.0%}. "
            f"Priority candidate for removal or rewrite."
        )


@dataclass
class PromptIssue(Recommendation):
    """A prompt pattern that leads to poor answers."""
    prompt_version: str = ""
    failure_rate: float = 0.0
    examples: list[dict] = field(default_factory=list)

    def __post_init__(self):
        super().__post_init__()
        self.type = RecommendationType.PROMPT_ISSUE
        self.severity = RecommendationSeverity.HIGH
        self.title = f"Prompt Issue: v{prompt_version}"
        self.description = f"Prompt version {prompt_version} has {failure_rate:.0%} failure rate."


@dataclass
class RoutingIssue(Recommendation):
    """An intent that is frequently misclassified."""
    intent: str = ""
    matched_rule: str = ""
    misrouted_count: int = 1
    expected_intent: str = ""

    def __post_init__(self):
        super().__post_init__()
        self.type = RecommendationType.ROUTING_ISSUE
        self.severity = RecommendationSeverity.MEDIUM
        self.title = f"Routing Issue: {self.intent}"
        self.description = (
            f"{self.matched_rule} → {self.intent}: {self.misrouted_count} queries may be misrouted. "
            f"Expected: {self.expected_intent}."
        )


@dataclass
class BenchmarkCandidate(Recommendation):
    """A high-frequency query that should be added to the benchmark dataset."""
    topic: str = ""
    frequency: int = 1

    def __post_init__(self):
        super().__post_init__()
        self.type = RecommendationType.BENCHMARK_CANDIDATE
        self.severity = RecommendationSeverity.LOW
        self.title = f"Benchmark Candidate: \"{self.topic[:60]}\""
        self.description = f"Asked {self.frequency}x. Add to eval dataset to track over time."
