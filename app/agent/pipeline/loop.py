"""Stage 2c': Controlled Agent Execution Loop (V3.12)

Moves execution from "execute everything once" to

    Plan → execute → inspect state → execute next eligible step

bounded and deterministic. Each iteration:

    find eligible step
        ↓
    (dependencies remain authoritative)
        ↓
    (capability policy V3.10)
        ↓
    (tool selection V3.11)
        ↓
    execute ONE step (Executor.execute_one)
        ↓
    update AgentState
        ↓
    evaluate next eligible step

Safety limits (limits are injectable for testing; defaults are hard caps):
    MAX_STEPS      = 10  — plans larger than this are rejected outright
    MAX_ITERATIONS = 10  — hard cap on loop iterations. No infinite loops.

Stop conditions (deterministic `stopped_reason`):
    - all steps completed
    - a step fails / is blocked (capability / tool policy, or blocked
      dependency) with NO independent step left executable
    - request cancelled (operator) or request timed out (V4.11)
    - maximum iterations reached
    - no executable step remains

V3.12 is NOT autonomous reasoning:
    - no reflection, no self-replanning, no automatic retries,
      no recursive LLM calls, no parallel execution, no new tools.
    - the loop only executes the existing approved plan.
    - the same authoritative V3.10 capability selections and V3.11 tool
      selections are passed to the executor for EVERY step — the loop can
      never bypass them.

V4.11 (partial execution recovery + cancellation) [additive]:
    - a failed/blocked step does not abort the whole run when independent
      steps remain: dependants are marked blocked (never executed) and
      independent steps continue once. When nothing independent remains,
      the loop stops with the SAME `step N failed|blocked` reason V3.12
      produced — behavior with no independents is unchanged.
    - the loop checks cancellation and request-timeout before every
      iteration; remaining steps are settled as blocked with
      step_cancelled / step_blocked events and one request_cancelled /
      request_timeout event per run. No step is retried or replanned.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from app.core.langsmith import traceable
from app.agent.pipeline.planner import Plan, PlanStep
from app.agent.pipeline.capabilities import CapabilitySelection
from app.agent.pipeline.tool_selection import ToolSelection
from app.agent.pipeline.state import (
    mark_request_cancelled,
    mark_request_timed_out,
    mark_step_blocked,
)
from app.agent.pipeline.trace import record_trace
from app.agent.pipeline.reliability import (
    REASON_REQUEST_CANCELLED,
    REASON_REQUEST_TIMED_OUT,
    is_cancel_requested,
    reliability_guard_of,
)
from app.agent.pipeline.executor import (
    Executor,
    ExecutionResult,
    StepResult,
    build_execution_result,
)

logger = logging.getLogger(__name__)


# ── Outcome model ────────────────────────────────────────────────────────────

@dataclass
class LoopResult:
    """Structured outcome of one bounded execution loop run."""
    completed: bool
    iterations: int
    stopped_reason: str
    # Additive: the aggregated ExecutionResult for downstream stages
    # (synthesis/validation). Never None after a run of a non-empty plan.
    execution: Optional[ExecutionResult] = None


class AgentExecutionLoop:
    """
    V3.12 bounded, deterministic execution loop.

    Pure orchestrator over Executor.execute_one — owns scheduling/limits only,
    never business logic, never tools.
    """

    MAX_STEPS = 10
    MAX_ITERATIONS = 10

    def __init__(
        self,
        executor: Optional[Executor] = None,
        max_steps: Optional[int] = None,
        max_iterations: Optional[int] = None,
    ) -> None:
        self._executor = executor if executor is not None else Executor()
        self._max_steps = max_steps if max_steps is not None else self.MAX_STEPS
        self._max_iterations = (
            max_iterations if max_iterations is not None else self.MAX_ITERATIONS
        )

    # ── Eligibility ──────────────────────────────────────────────────────────

    @staticmethod
    def _find_eligible(
        steps: list[PlanStep],
        step_status: dict[int, str],
    ) -> Optional[PlanStep]:
        """First (by step_id) not-yet-terminal step whose dependencies completed."""
        for step in steps:
            if step_status.get(step.step_id, "pending") not in ("pending",):
                continue
            if all(step_status.get(dep, "pending") == "completed" for dep in step.dependencies):
                return step
        return None

    # ── Run ──────────────────────────────────────────────────────────────────

    @traceable(name="agent_execution_loop", metadata={"stage": "2c'"})
    def run(
        self,
        plan: Optional[Plan],
        context: object = None,
        capability_selections: Optional[list[CapabilitySelection]] = None,
        tool_selections: Optional[list[ToolSelection]] = None,
    ) -> LoopResult:
        """
        Execute the approved plan one eligible step per iteration.

        Deterministic, bounded (MAX_STEPS / MAX_ITERATIONS). Never executes
        more than one step at a time, never retries, never replans.

        Args:
            plan: The approved Plan (V3.2).
            context: PipelineContext ('agent_state' is updated per iteration).
            capability_selections: V3.10 authoritative selections (unchanged).
            tool_selections: V3.11 authoritative selections (unchanged).
        """
        steps: list[PlanStep] = []
        if plan is not None and plan.steps:
            steps = sorted(plan.steps, key=lambda s: s.step_id)

        if not steps:
            return LoopResult(
                completed=True,
                iterations=0,
                stopped_reason="empty plan",
                execution=build_execution_result([], {}),
            )

        if len(steps) > self._max_steps:
            return LoopResult(
                completed=False,
                iterations=0,
                stopped_reason=f"plan exceeds max steps ({self._max_steps})",
                execution=build_execution_result([], {}),
            )

        step_status: dict[int, str] = {}
        step_outputs: dict[int, str] = {}
        step_results: dict[int, StepResult] = {}
        iterations = 0

        # V4.11: first failed/blocked outcome drives the final reason when
        # the run ends with no executable step left (preserves the exact
        # V3.12 `step N failed|blocked` reason strings).
        terminal_reason: Optional[str] = None

        while True:
            # 1. All steps completed?
            if all(step_status.get(s.step_id) == "completed" for s in steps):
                return self._finish(True, iterations, "all steps completed",
                                    steps, step_results, step_outputs)

            # 1a. V4.11: cooperative cancellation (operator intent wins).
            if is_cancel_requested(context):
                self._settle_remaining(
                    "cancelled", REASON_REQUEST_CANCELLED,
                    steps, step_status, step_results, context,
                )
                return self._finish(False, iterations, "request cancelled",
                                    steps, step_results, step_outputs)

            # 1b. V4.11: request-level timeout.
            guard = reliability_guard_of(context)
            if guard is not None and guard.request_expired():
                self._settle_remaining(
                    "timed_out", REASON_REQUEST_TIMED_OUT,
                    steps, step_status, step_results, context,
                )
                return self._finish(False, iterations, "request timed out",
                                    steps, step_results, step_outputs)

            # 2. Hard iteration cap. No infinite loops.
            if iterations >= self._max_iterations:
                return self._finish(False, iterations, "max iterations reached",
                                    steps, step_results, step_outputs)

            # 3. Find the next eligible step (dependencies authoritative).
            step = self._find_eligible(steps, step_status)
            if step is None:
                # V4.11: with no step left executable, prefer the first
                # failure/block as the reason (deterministic, V3.12-compatible).
                reason = terminal_reason or "no executable step remains"
                return self._finish(False, iterations, reason,
                                    steps, step_results, step_outputs)

            # 4. Execute ONE step through the executor (full V3.10/V3.11
            #    enforcement applied inside execute_one — never bypassed).
            iterations += 1
            result = self._executor.execute_one(
                step,
                context=context,
                capability_selections=capability_selections,
                tool_selections=tool_selections,
                step_status=step_status,
                step_outputs=step_outputs,
            )
            step_status[step.step_id] = result.status
            step_results[step.step_id] = result
            if result.status == "completed":
                step_outputs[step.step_id] = result.output

            logger.info(
                "execution_loop iteration=%d step_id=%d status=%s",
                iterations, step.step_id, result.status,
            )

            # 5. V4.11 partial execution recovery: a failed/blocked step
            #    blocks its dependants (never executed) but independent
            #    steps may still run. No retry, no replan.
            if result.status in ("failed", "blocked"):
                if terminal_reason is None:
                    terminal_reason = f"step {step.step_id} {result.status}"
                self._block_dependants(steps, step_status, step_results, context)

    # ── V4.11: settle remaining steps (cancellation / timeout) ───────────────

    def _settle_remaining(
        self,
        cause: str,
        reason: str,
        steps: list[PlanStep],
        step_status: dict[int, str],
        step_results: dict[int, StepResult],
        context: object,
    ) -> None:
        """Mark every not-yet-settled step blocked (never left running/pending).

        Emits one per-step event (step_cancelled on cancellation, otherwise
        step_blocked) and one request-level event (request_cancelled /
        request_timeout). State flags are set through the lifecycle helpers.
        """
        for s in steps:
            if step_status.get(s.step_id, "pending") != "pending":
                continue
            step_status[s.step_id] = "blocked"
            step_results[s.step_id] = StepResult(
                step_id=s.step_id,
                status="blocked",
                output="",
                error=reason,
                tool=s.tool,
            )
            agent_state = getattr(context, "agent_state", None) if context else None
            if agent_state:
                mark_step_blocked(agent_state, s.step_id, reason)
            record_trace(
                context, "execution",
                "step_cancelled" if cause == "cancelled" else "step_blocked",
                status="blocked", step_id=s.step_id, tool=s.tool or "",
            )
        agent_state = getattr(context, "agent_state", None) if context else None
        if agent_state:
            if cause == "cancelled":
                mark_request_cancelled(agent_state)
            else:
                mark_request_timed_out(agent_state)
        record_trace(
            context, "execution",
            "request_cancelled" if cause == "cancelled" else "request_timeout",
            status="blocked",
            step_id=None, tool="",
        )

    # ── V4.11: block dependants of terminal failures ─────────────────────────

    def _block_dependants(
        self,
        steps: list[PlanStep],
        step_status: dict[int, str],
        step_results: dict[int, StepResult],
        context: object,
    ) -> None:
        """Mark pending steps with a failed/blocked dependency as blocked.

        They are never handed to the executor (the loop's eligibility rule
        already requires completed dependencies; this pass settles them so
        the final ExecutionResult carries their outcome).
        """
        for s in steps:
            if step_status.get(s.step_id, "pending") != "pending":
                continue
            if any(
                step_status.get(dep) not in (None, "completed")
                for dep in s.dependencies
            ):
                error = (
                    f"Blocked: dependency step(s) {s.dependencies} "
                    "did not complete successfully."
                )
                step_status[s.step_id] = "blocked"
                step_results[s.step_id] = StepResult(
                    step_id=s.step_id,
                    status="blocked",
                    output="",
                    error=error,
                    tool=s.tool,
                )
                agent_state = getattr(context, "agent_state", None) if context else None
                if agent_state:
                    mark_step_blocked(agent_state, s.step_id, error)
                record_trace(
                    context, "execution", "step_blocked",
                    status="blocked", step_id=s.step_id, tool=s.tool or "",
                )

    @staticmethod
    def _finish(
        completed: bool,
        iterations: int,
        reason: str,
        steps: list[PlanStep],
        step_results: dict[int, StepResult],
        step_outputs: dict[int, str],
    ) -> LoopResult:
        ordered = [step_results[s.step_id] for s in steps if s.step_id in step_results]
        return LoopResult(
            completed=completed,
            iterations=iterations,
            stopped_reason=reason,
            execution=build_execution_result(ordered, step_outputs),
        )