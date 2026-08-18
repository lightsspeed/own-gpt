"""
V3.5: Agent Execution State & Observability

Purpose: Provide a structured, observable representation of the complete
agent request lifecycle — from intent classification through plan execution
and synthesis.

Key invariants:
  - State is READ-ONLY from the outside. Only the lifecycle helpers below mutate it.
  - State never executes tools, triggers retrieval, or modifies memory.
  - Timing uses perf_counter() monotonic clock for deterministic durations.
  - to_dict() and summary() are always safe to call and never raise.
  - Transition guards prevent silent backward transitions (e.g. completed → running).
  - No new persistence, telemetry, or logging framework is introduced.

Lifecycle:
    pending → running → completed | failed | partial
    (for each step: pending → running → completed | failed | blocked)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ── Allowed status sets ───────────────────────────────────────────────────────

ALLOWED_STEP_STATUSES = frozenset({"pending", "running", "completed", "failed", "blocked"})
ALLOWED_EXEC_STATUSES = frozenset({"pending", "running", "completed", "failed", "partial"})
ALLOWED_SYNTH_STATUSES = frozenset({"pending", "running", "completed", "failed"})

# Transitions that are *not* permitted (prevents silent backward movement)
_INVALID_STEP_TRANSITIONS: frozenset[tuple[str, str]] = frozenset({
    ("completed", "running"),
    ("completed", "pending"),
    ("failed", "running"),
    ("failed", "pending"),
    ("blocked", "running"),
    ("blocked", "pending"),
})


# ── Step Execution State ──────────────────────────────────────────────────────

@dataclass
class StepExecutionState:
    """Runtime state of a single plan step during execution."""
    step_id: int
    status: str = "pending"             # pending | running | completed | failed | blocked
    started_at: Optional[float] = None  # perf_counter timestamp
    completed_at: Optional[float] = None
    duration_ms: Optional[float] = None
    output: Optional[str] = None
    error: Optional[str] = None
    tool: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "output_preview": self.output[:200] if self.output else None,
            "error": self.error,
            "tool": self.tool,
        }


# ── Agent State ───────────────────────────────────────────────────────────────

@dataclass
class AgentState:
    """
    Structured observable state for a single agent request.

    Covers the full lifecycle:
        Intent → Route → Plan → Execute → Synthesize
    """
    request_id: str
    question: str

    # Stage outputs (populated progressively)
    intent: Optional[str] = None
    intent_confidence: Optional[float] = None
    route: Optional[str] = None
    goal: Optional[str] = None
    plan_steps: int = 0

    # Execution tracking
    current_step: Optional[int] = None
    steps: list[StepExecutionState] = field(default_factory=list)
    execution_status: str = "pending"   # pending | running | completed | failed | partial
    synthesis_status: Optional[str] = None  # pending | running | completed | failed

    # V4.11: request-level reliability flags (set only by the lifecycle
    # helpers below — never mutated directly from the outside).
    cancelled: bool = False
    request_timed_out: bool = False

    # Timing (perf_counter monotonic)
    started_at: float = field(default_factory=time.perf_counter)
    completed_at: Optional[float] = None
    total_duration_ms: Optional[float] = None

    def to_dict(self) -> dict:
        """Serialize the full agent state to a plain dictionary."""
        return {
            "request_id": self.request_id,
            "question": self.question[:200] if self.question else "",
            "intent": self.intent,
            "intent_confidence": self.intent_confidence,
            "route": self.route,
            "goal": self.goal,
            "plan_steps": self.plan_steps,
            "current_step": self.current_step,
            "steps": [s.to_dict() for s in self.steps],
            "execution_status": self.execution_status,
            "synthesis_status": self.synthesis_status,
            "cancelled": self.cancelled,
            "request_timed_out": self.request_timed_out,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "total_duration_ms": self.total_duration_ms,
        }

    def summary(self) -> str:
        """
        Compact human-readable summary safe for logging.
        Never includes full step outputs or sensitive data.
        """
        completed_count = sum(1 for s in self.steps if s.status == "completed")
        failed_count    = sum(1 for s in self.steps if s.status == "failed")
        blocked_count   = sum(1 for s in self.steps if s.status == "blocked")
        dur = f"{self.total_duration_ms:.1f}" if self.total_duration_ms is not None else "?"

        return (
            f"request={self.request_id} "
            f"intent={self.intent or '?'} "
            f"route={self.route or '?'} "
            f"steps={self.plan_steps} "
            f"completed={completed_count} "
            f"failed={failed_count} "
            f"blocked={blocked_count} "
            f"status={self.execution_status} "
            f"duration_ms={dur}"
        )


# ── Step Lifecycle Helpers ────────────────────────────────────────────────────
#
# Centralise all state mutations here. The executor/synthesizer call these
# rather than directly mutating AgentState, keeping transitions auditable.

def _get_step(state: AgentState, step_id: int) -> Optional[StepExecutionState]:
    for s in state.steps:
        if s.step_id == step_id:
            return s
    return None


def _guard_transition(step: StepExecutionState, new_status: str) -> bool:
    """
    Returns True if the transition is allowed.
    Logs a warning and returns False for invalid transitions.
    """
    if (step.status, new_status) in _INVALID_STEP_TRANSITIONS:
        logger.warning(
            "agent_state.invalid_transition step_id=%d %s→%s ignored",
            step.step_id, step.status, new_status,
        )
        return False
    return True


def mark_step_started(state: AgentState, step_id: int, tool: Optional[str] = None) -> None:
    """Transition step: pending → running. Records start timestamp."""
    step = _get_step(state, step_id)
    if step is None:
        logger.warning("mark_step_started: unknown step_id=%d", step_id)
        return
    if not _guard_transition(step, "running"):
        return
    step.status = "running"
    step.started_at = time.perf_counter()
    if tool is not None:
        step.tool = tool
    state.current_step = step_id
    state.execution_status = "running"
    logger.debug(
        "agent.step.started request_id=%s step_id=%d tool=%s",
        state.request_id, step_id, tool,
    )


def mark_step_completed(
    state: AgentState, step_id: int, output: Optional[str] = None
) -> None:
    """Transition step: running → completed. Records duration."""
    step = _get_step(state, step_id)
    if step is None:
        logger.warning("mark_step_completed: unknown step_id=%d", step_id)
        return
    if not _guard_transition(step, "completed"):
        return
    now = time.perf_counter()
    step.status = "completed"
    step.completed_at = now
    step.output = output
    if step.started_at is not None:
        step.duration_ms = (now - step.started_at) * 1000
    logger.debug(
        "agent.step.completed request_id=%s step_id=%d duration_ms=%s tool=%s",
        state.request_id, step_id,
        f"{step.duration_ms:.2f}" if step.duration_ms else "?",
        step.tool,
    )


def mark_step_failed(
    state: AgentState, step_id: int, error: Optional[str] = None
) -> None:
    """Transition step: running → failed. Records error and duration."""
    step = _get_step(state, step_id)
    if step is None:
        logger.warning("mark_step_failed: unknown step_id=%d", step_id)
        return
    if not _guard_transition(step, "failed"):
        return
    now = time.perf_counter()
    step.status = "failed"
    step.completed_at = now
    step.error = error
    if step.started_at is not None:
        step.duration_ms = (now - step.started_at) * 1000
    logger.debug(
        "agent.step.failed request_id=%s step_id=%d error=%s",
        state.request_id, step_id, (error or "")[:120],
    )


def mark_step_blocked(
    state: AgentState, step_id: int, reason: Optional[str] = None
) -> None:
    """Transition step: pending → blocked (dependency not met)."""
    step = _get_step(state, step_id)
    if step is None:
        logger.warning("mark_step_blocked: unknown step_id=%d", step_id)
        return
    if not _guard_transition(step, "blocked"):
        return
    step.status = "blocked"
    step.error = reason
    logger.debug(
        "agent.step.blocked request_id=%s step_id=%d reason=%s",
        state.request_id, step_id, (reason or "")[:120],
    )


def mark_request_cancelled(state: AgentState) -> None:
    """V4.11: flag a cooperatively cancelled request (terminal, additive)."""
    state.cancelled = True


def mark_request_timed_out(state: AgentState) -> None:
    """V4.11: flag a request that exceeded its timeout (terminal, additive)."""
    state.request_timed_out = True


def finalize_execution_status(state: AgentState) -> None:
    """
    Compute and set the overall execution_status from step states.
    Must be called after all steps have been processed.

    Rules (deterministic):
      all completed                          → completed
      ≥1 completed AND ≥1 failed/blocked     → partial
      no steps completed (failed/blocked)    → failed
      no steps at all                        → completed (vacuously)
    """
    if not state.steps:
        state.execution_status = "completed"
        return

    completed = [s for s in state.steps if s.status == "completed"]
    failed    = [s for s in state.steps if s.status == "failed"]
    blocked   = [s for s in state.steps if s.status == "blocked"]

    if completed and not failed and not blocked:
        state.execution_status = "completed"
    elif completed and (failed or blocked):
        state.execution_status = "partial"
    else:
        state.execution_status = "failed"


def finalize_timing(state: AgentState) -> None:
    """Record completed_at and total_duration_ms on the state."""
    now = time.perf_counter()
    state.completed_at = now
    state.total_duration_ms = (now - state.started_at) * 1000
    logger.debug(
        "agent.request.completed request_id=%s duration_ms=%.2f status=%s",
        state.request_id, state.total_duration_ms, state.execution_status,
    )
