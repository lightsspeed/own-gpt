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
    - a required step fails
    - a step is blocked (capability / tool policy, or blocked dependency)
    - maximum iterations reached
    - no executable step remains

V3.12 is NOT autonomous reasoning:
    - no reflection, no self-replanning, no automatic retries,
      no recursive LLM calls, no parallel execution, no new tools.
    - the loop only executes the existing approved plan.
    - the same authoritative V3.10 capability selections and V3.11 tool
      selections are passed to the executor for EVERY step — the loop can
      never bypass them.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from app.core.langsmith import traceable
from app.agent.pipeline.planner import Plan, PlanStep
from app.agent.pipeline.capabilities import CapabilitySelection
from app.agent.pipeline.tool_selection import ToolSelection
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

        while True:
            # 1. All steps completed?
            if all(step_status.get(s.step_id) == "completed" for s in steps):
                return self._finish(True, iterations, "all steps completed",
                                    steps, step_results, step_outputs)

            # 2. Hard iteration cap. No infinite loops.
            if iterations >= self._max_iterations:
                return self._finish(False, iterations, "max iterations reached",
                                    steps, step_results, step_outputs)

            # 3. Find the next eligible step (dependencies authoritative).
            step = self._find_eligible(steps, step_status)
            if step is None:
                return self._finish(False, iterations, "no executable step remains",
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

            # 5. A required step failing or blocking ends the run immediately.
            if result.status in ("failed", "blocked"):
                return self._finish(False, iterations,
                                    f"step {step.step_id} {result.status}",
                                    steps, step_results, step_outputs)

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