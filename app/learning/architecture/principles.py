"""
Architecture principles — modeled as data so modules can reference them directly.

Each principle declares:
  - id (machine-readable, e.g. PRINCIPLE_001)
  - title
  - description
  - mandatory (True = guardrail enforced)
  - stage (which lifecycle stage this principle governs)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .lifecycle import LifecycleStage


@dataclass(frozen=True)
class Principle:
    id: str
    title: str
    description: str
    mandatory: bool = True
    stage: Optional[LifecycleStage] = None


# ── Core Principles ──────────────────────────────────────────────────────

PRINCIPLES: list[Principle] = [
    Principle(
        id="PRINCIPLE_001",
        title="Every observation is persisted",
        description="All production interactions (queries, retrievals, generations, user feedback) are recorded in the Learning Ledger before any analysis occurs.",
        mandatory=True,
        stage=LifecycleStage.OBSERVE,
    ),
    Principle(
        id="PRINCIPLE_002",
        title="Every conclusion is evidence-backed",
        description="All Findings must reference specific Evidence (observations, sample sizes, supporting record IDs). A Finding without evidence is invalid.",
        mandatory=True,
        stage=LifecycleStage.EXPLAIN,
    ),
    Principle(
        id="PRINCIPLE_003",
        title="Every recommendation is derived from findings",
        description="Recommendations are a presentation layer over Findings. Every Recommendation must reference the Finding that produced it.",
        mandatory=True,
        stage=LifecycleStage.PROPOSE,
    ),
    Principle(
        id="PRINCIPLE_004",
        title="Every optimization is validated offline",
        description="Experiments run against replay data and benchmarks, never against production traffic. No parameter change may skip validation.",
        mandatory=True,
        stage=LifecycleStage.VALIDATE,
    ),
    Principle(
        id="PRINCIPLE_005",
        title="Every production change is human-approved and traceable",
        description="Approved changes must link back through Experiment → Recommendation → Finding → Evidence. No blind auto-deployment.",
        mandatory=True,
        stage=LifecycleStage.APPLY,
    ),
    Principle(
        id="PRINCIPLE_006",
        title="No artifact may skip lifecycle stages",
        description="Every artifact must respect the OBSERVE → MEASURE → EXPLAIN → PROPOSE → VALIDATE → APPLY ordering. Stage-skipping is a validation error.",
        mandatory=True,
    ),
    Principle(
        id="PRINCIPLE_007",
        title="Separation of learning from changing",
        description="Analytics, Evidence, and Recommendations are read-only. They observe and explain but never modify production state. Only human-approved Decisions may trigger changes.",
        mandatory=True,
        stage=LifecycleStage.APPLY,
    ),
    Principle(
        id="PRINCIPLE_008",
        title="Evidence quality is measurable",
        description="Every Evidence object carries a multi-dimensional strength score (sample_size, agreement, trend, consistency, confidence). Raw scores are always visible.",
        mandatory=False,
        stage=LifecycleStage.EXPLAIN,
    ),
]


def get_principle(pid: str) -> Principle:
    for p in PRINCIPLES:
        if p.id == pid:
            return p
    raise KeyError(f"Unknown principle: {pid}")
