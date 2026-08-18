"""
V4.6 — Agent Memory & Execution Continuity

Structured, dependency-scoped execution context for plan steps.

Design invariants:
  - A step receives ONLY outputs from its DECLARED dependencies.
    No unrelated step output ever leaks into a step's context.
  - Dependency ordering is preserved: entries appear in the same order
    as the step's `dependencies` list.
  - Context size is bounded: each propagated output is truncated at
    `max_output_chars`; structured metadata survives truncation.
  - Lineage is preserved: every entry retains its originating `step_id`
    and `execution_id`, exposed via `StepContext.lineage()` and attached
    to the owning StepResult for synthesis and audit.
  - This module REUSES existing Memory V2 (persistent user facts) and
    AgentState (transient execution state). It introduces NO new memory
    or vector store — it only shapes information that already flows.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Default per-output propagation bound for dependency context.
DEFAULT_MAX_OUTPUT_CHARS = 4000


@dataclass
class ContextEntry:
    """One propagated dependency output, with lineage metadata.

    Structured metadata (step_id, execution_id, session_id, truncation
    flags, origin_length) is preserved even when the raw output is
    truncated to respect the size bound.
    """

    step_id: int
    output: str
    execution_id: str = ""
    session_id: str = ""
    truncated: bool = False
    origin_length: int = 0

    @property
    def output_length(self) -> int:
        return len(self.output)

    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "execution_id": self.execution_id,
            "session_id": self.session_id,
            "truncated": self.truncated,
            "origin_length": self.origin_length,
            "output_length": self.output_length,
        }


@dataclass
class StepContext:
    """Structured, dependency-scoped context for ONE plan step.

    Carries execution identity (request_id, execution_id, session_id,
    project_id) plus an ordered list of ContextEntry objects — only the
    declared dependencies' completed outputs, never unrelated steps.
    """

    step_id: int
    request_id: str = ""
    execution_id: str = ""
    session_id: str = ""
    project_id: str = ""
    entries: list[ContextEntry] = field(default_factory=list)

    def add(self, entry: ContextEntry) -> None:
        self.entries.append(entry)

    def to_plain_text(self) -> str:
        """Render the handler-facing wire format.

        Identical layout to the V3.3 dependency context string:
        "[Step <id>]\\n<output>" joined by "\\n\\n". Handlers are
        unchanged; the structure now exists behind the strings.
        """
        parts = [f"[Step {entry.step_id}]\n{entry.output}" for entry in self.entries]
        return "\n\n".join(parts)

    def lineage(self) -> list[dict]:
        """Every propagated result's origin, for synthesis and audit."""
        return [entry.to_dict() for entry in self.entries]

    def total_chars(self) -> int:
        return sum(entry.output_length for entry in self.entries)

    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "request_id": self.request_id,
            "execution_id": self.execution_id,
            "session_id": self.session_id,
            "project_id": self.project_id,
            "entries": [entry.to_dict() for entry in self.entries],
        }


class StepContextBuilder:
    """Builds a dependency-scoped StepContext for a single plan step.

    Propagates ONLY outputs of the step's declared dependencies, in
    declared order. Missing or failed dependency outputs are skipped
    (never injected as stale/empty entries). Outputs beyond
    `max_output_chars` are truncated; metadata survives truncation.
    """

    def __init__(self, max_output_chars: int = DEFAULT_MAX_OUTPUT_CHARS):
        if max_output_chars < 1:
            raise ValueError("max_output_chars must be >= 1")
        self.max_output_chars = max_output_chars

    def build(
        self,
        step,
        step_outputs: dict[int, str],
        request_id: str = "",
        execution_id: str = "",
        session_id: str = "",
        project_id: str = "",
        step_status: Optional[dict[int, str]] = None,
    ) -> StepContext:
        """Construct the StepContext for `step`.

        Args:
            step: the PlanStep being executed (its `dependencies` and
                `step_id` define the context scope).
            step_outputs: outputs of already-completed steps.
            request_id: identity of the agent request.
            execution_id: identity of the execution run.
            session_id, project_id: execution identity metadata.
            step_status: optional map of step_id -> status; only
                "completed" dependencies are propagated.
        """
        step_status = step_status or {}
        ctx = StepContext(
            step_id=step.step_id,
            request_id=request_id,
            execution_id=execution_id,
            session_id=session_id,
            project_id=project_id,
        )
        for dep_id in step.dependencies:
            if step_status.get(dep_id, "completed") != "completed":
                logger.debug(
                    "step_context step_id=%d dependency=%d status=%s skipped (not completed)",
                    step.step_id, dep_id, step_status.get(dep_id),
                )
                continue
            dep_out = step_outputs.get(dep_id, "")
            if not dep_out:
                logger.debug(
                    "step_context step_id=%d dependency=%d output empty, skipped",
                    step.step_id, dep_id,
                )
                continue
            truncated = len(dep_out) > self.max_output_chars
            shown = dep_out[: self.max_output_chars] if truncated else dep_out
            ctx.add(ContextEntry(
                step_id=dep_id,
                output=shown,
                execution_id=execution_id,
                session_id=session_id,
                truncated=truncated,
                origin_length=len(dep_out),
            ))
        return ctx