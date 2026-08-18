"""
Stage 2c: Plan Executor (V3.3)

Purpose: Execute the Plan produced by V3.2 in dependency-aware order,
dispatching each PlanStep to the appropriate existing OwnGPT capability.

Key architectural invariants:
  - Executor orchestrates; it NEVER contains business logic for tools.
  - All tool calls route through tool_gate.py (guardrail + audit).
  - Project isolation, memory isolation, source policy, and citations
    are all enforced by the underlying capability — NOT bypassed here.
  - No autonomous retry, reflection, replanning, self-correction, or
    parallel execution in V3.3.
  - V3.10: capability selections are authoritative — a step denied by the
    CapabilitySelector (or a step with no selection) is BLOCKED before any
    handler or tool runs. Fail closed.
  - V3.11: tool selections are authoritative too — the executor executes only
    the VALIDATED tool + arguments chosen by the ToolSelector, never a tool
    the selector rejected (fail closed). Denied capability ⇒ cannot execute,
    even if a tool was somehow requested.
  - V3.12: execute_one() executes a SINGLE step with full enforcement; the
    AgentExecutionLoop drives one eligible step per iteration through it.

Step execution order:
  1. Build a dependency-aware execution queue.
  2. Execute each step only after all its declared dependencies have succeeded.
  3. If a dependency fails, mark dependants as BLOCKED (not executed).
  4. Pass accumulated dependency outputs as context into each step.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

from app.agent.pipeline.planner import Plan, PlanStep
from app.agent.pipeline.capabilities import CapabilitySelection
from app.agent.pipeline.tool_selection import ToolSelection
from app.agent.pipeline.state import (
    mark_step_started,
    mark_step_completed,
    mark_step_failed,
    mark_step_blocked,
)

# Eager top-level imports — required for hermetic patching in unit tests.
# Handlers use these as the canonical reference point so mock.patch works cleanly.
from app.agent.tool_gate import request_tool_execution  # noqa: E402
from app.core.llm_provider import build_llm             # noqa: E402

logger = logging.getLogger(__name__)


# ── Execution Models ─────────────────────────────────────────────────────────

VALID_STEP_STATUSES = frozenset({"pending", "running", "completed", "failed", "blocked"})
VALID_EXEC_STATUSES = frozenset({"completed", "partial", "failed", "blocked"})


@dataclass
class StepResult:
    step_id: int
    status: str         # pending | running | completed | failed | blocked
    output: str = ""
    error: Optional[str] = None
    tool: Optional[str] = None


@dataclass
class ExecutionResult:
    status: str                         # completed | partial | failed | blocked
    step_results: list[StepResult] = field(default_factory=list)
    outputs: dict[int, str] = field(default_factory=dict)
    final_output: Optional[str] = None
    error: Optional[str] = None


# ── Action Handlers ───────────────────────────────────────────────────────────
# Each handler receives (step, context_str, pipeline_ctx, tool_selection) and
# returns a str. When a V3.11 ToolSelection is provided it is authoritative:
# the handler executes exactly the selected tool with the selected arguments.
# Handlers MUST use existing tool_impls / tool_gate, not implement tools here.

ActionHandler = Callable[["PlanStep", str, object, Optional[ToolSelection]], str]


def _handle_memory(
    step: PlanStep,
    context: str,
    pipeline_ctx: object,
    tool_selection: Optional[ToolSelection] = None,
) -> str:
    """Route to the existing memory tool via tool_gate guardrail."""
    question = getattr(pipeline_ctx, "question", "") if pipeline_ctx else ""
    user_id = getattr(pipeline_ctx, "user_id", "") if pipeline_ctx else ""
    project_id = getattr(pipeline_ctx, "project_id", "") if pipeline_ctx else ""
    session_id = getattr(pipeline_ctx, "session_id", "") if pipeline_ctx else ""

    if tool_selection is not None:
        # V3.11: validated tool + arguments are authoritative.
        tool = tool_selection.tool or "remember_user_fact"
        args = dict(tool_selection.arguments or {})
    else:
        tool = step.tool or "remember_user_fact"
        args: dict = {"fact": step.description or question}
        if user_id:
            args["user_id"] = str(user_id)
        if project_id:
            args["project_id"] = str(project_id)
        if session_id and tool == "remember_session_fact":
            args["session_id"] = str(session_id)

    execution = request_tool_execution(tool, args)
    if execution.status in ("executed", "allowed"):
        return execution.result or f"Memory tool '{tool}' completed."
    if execution.status == "denied":
        raise RuntimeError(f"Memory tool denied by guardrail: {execution.error}")
    if execution.status == "pending":
        return f"Memory tool '{tool}' queued for operator approval."
    raise RuntimeError(f"Memory tool '{tool}' failed: {execution.error}")


def _handle_knowledge(
    step: PlanStep,
    context: str,
    pipeline_ctx: object,
    tool_selection: Optional[ToolSelection] = None,
) -> str:
    """Route to the existing RAG knowledge base via tool_gate (project-scoped)."""
    p_context = getattr(pipeline_ctx, "context", None)
    if p_context and p_context.knowledge_context:
        return p_context.knowledge_context

    if tool_selection is not None:
        # V3.11: validated tool + arguments are authoritative.
        tool = tool_selection.tool or "search_knowledge_base"
        args: dict = dict(tool_selection.arguments or {})
    else:
        question = getattr(pipeline_ctx, "question", "") if pipeline_ctx else ""
        project_id = getattr(pipeline_ctx, "project_id", "") if pipeline_ctx else ""
        final_query = getattr(pipeline_ctx, "final_query", "") if pipeline_ctx else ""

        query = final_query or question or step.description
        tool = "search_knowledge_base"
        args = {"query": query, "project_id": str(project_id) if project_id else ""}

    execution = request_tool_execution(tool, args)
    if execution.status in ("executed", "allowed"):
        return execution.result or "No relevant knowledge base content found."
    raise RuntimeError(f"Knowledge search failed: {execution.error}")


def _handle_document(
    step: PlanStep,
    context: str,
    pipeline_ctx: object,
    tool_selection: Optional[ToolSelection] = None,
) -> str:
    """Document retrieval — same as knowledge, scoped to uploaded documents."""
    p_context = getattr(pipeline_ctx, "context", None)
    if p_context and p_context.document_context:
        return p_context.document_context
    return _handle_knowledge(step, context, pipeline_ctx, tool_selection)


def _handle_web_search(
    step: PlanStep,
    context: str,
    pipeline_ctx: object,
    tool_selection: Optional[ToolSelection] = None,
) -> str:
    """Route to the existing Tavily web search via tool_gate."""
    p_context = getattr(pipeline_ctx, "context", None)
    if p_context and p_context.web_context:
        return p_context.web_context

    if tool_selection is not None:
        # V3.11: validated tool + arguments are authoritative.
        tool = tool_selection.tool or "web_search"
        args: dict = dict(tool_selection.arguments or {})
    else:
        question = getattr(pipeline_ctx, "question", "") if pipeline_ctx else ""
        query = step.description or question
        tool = "web_search"
        args = {"query": query}

    execution = request_tool_execution(tool, args)
    if execution.status in ("executed", "allowed"):
        return execution.result or "No web search results found."
    raise RuntimeError(f"Web search failed: {execution.error}")


def _handle_coding(
    step: PlanStep,
    context: str,
    pipeline_ctx: object,
    tool_selection: Optional[ToolSelection] = None,
) -> str:
    """Code generation — uses LLM reasoning over question + dependency context."""
    return _handle_direct_answer(step, context, pipeline_ctx, tool_selection)


def _handle_reasoning(
    step: PlanStep,
    context: str,
    pipeline_ctx: object,
    tool_selection: Optional[ToolSelection] = None,
) -> str:
    """Multi-step reasoning — uses LLM over question + dependency outputs."""
    return _handle_direct_answer(step, context, pipeline_ctx, tool_selection)


def _handle_direct_answer(
    step: PlanStep,
    context: str,
    pipeline_ctx: object,
    tool_selection: Optional[ToolSelection] = None,
) -> str:
    """LLM direct answer using existing llm_provider without triggering RAG."""
    from langchain_core.messages import HumanMessage, SystemMessage

    question = getattr(pipeline_ctx, "question", "") if pipeline_ctx else ""

    system = (
        "You are a helpful AI assistant. "
        "Use the provided context if relevant, then answer the user's question.\n\n"
        f"Context:\n{context}" if context.strip() else
        "You are a helpful AI assistant."
    )
    prompt = step.description or question or "Please provide a helpful response."

    llm = build_llm(temperature=0.3, max_tokens=1024)
    response = llm.invoke([
        SystemMessage(content=system),
        HumanMessage(content=prompt),
    ])
    content = response.content
    if isinstance(content, list):
        content = "".join(
            block.get("text", "") for block in content if isinstance(block, dict)
        )
    return str(content).strip()


# Registry maps action name → handler callable
_ACTION_HANDLERS: dict[str, ActionHandler] = {
    "memory":        _handle_memory,
    "knowledge":     _handle_knowledge,
    "document":      _handle_document,
    "web_search":    _handle_web_search,
    "coding":        _handle_coding,
    "reasoning":     _handle_reasoning,
    "direct_answer": _handle_direct_answer,
}


# ── Dependency-Aware Executor ─────────────────────────────────────────────────

def _blocked_result(step: PlanStep, reason: str, agent_state: object) -> StepResult:
    """Build a blocked StepResult without executing the step's handler."""
    result = StepResult(
        step_id=step.step_id,
        status="blocked",
        output="",
        error=reason,
        tool=step.tool,
    )
    logger.warning(
        "executor step_id=%d status=blocked reason=%s",
        step.step_id,
        reason,
    )
    if agent_state:
        mark_step_blocked(agent_state, step.step_id, reason)
    return result


def build_execution_result(
    step_results: list[StepResult],
    outputs: dict[int, str],
) -> ExecutionResult:
    """Aggregate per-step results into an ExecutionResult (single source)."""
    if not step_results:
        return ExecutionResult(
            status="completed",
            step_results=[],
            outputs={},
            final_output="No steps to execute.",
            error=None,
        )

    statuses = {r.status for r in step_results}

    if all(r.status == "completed" for r in step_results):
        overall_status = "completed"
    elif "completed" in statuses and ("failed" in statuses or "blocked" in statuses):
        overall_status = "partial"
    elif statuses == {"blocked"}:
        overall_status = "blocked"
    else:
        overall_status = "failed"

    # Final output is the last completed step's output, or the synthesis step.
    final_output = None
    for r in reversed(step_results):
        if r.status == "completed":
            final_output = outputs.get(r.step_id)
            break

    logger.info(
        "executor plan_completed overall_status=%s steps=%d completed=%d failed=%d blocked=%d",
        overall_status,
        len(step_results),
        sum(1 for r in step_results if r.status == "completed"),
        sum(1 for r in step_results if r.status == "failed"),
        sum(1 for r in step_results if r.status == "blocked"),
    )

    return ExecutionResult(
        status=overall_status,
        step_results=step_results,
        outputs=outputs,
        final_output=final_output,
        error=None,
    )


class Executor:
    """
    V3.3 Plan Executor.

    Executes PlanSteps in dependency-aware order. Respects step.dependencies —
    does NOT assume linear ordering alone is sufficient.

    Design constraints:
      - Does not retry, reflect, replan, or run in parallel.
      - Does not bypass tool_gate.py or guardrail.py.
      - Does not contain tool business logic (delegates to tool_impls / tool_gate).
      - No autonomous loop — executes once and returns ExecutionResult.
    """

    def execute(
        self,
        plan: Plan,
        context: object = None,
        capability_selections: Optional[list[CapabilitySelection]] = None,
        tool_selections: Optional[list[ToolSelection]] = None,
    ) -> ExecutionResult:
        """
        Execute all PlanSteps in dependency-aware order.

        Args:
            plan: The Plan produced by V3.2 Planner.
            context: The PipelineContext (optional). Provides user/session/project IDs.
            capability_selections: V3.10 authoritative capability selections.
                     When provided, a step without a selection, or a step whose
                     selection is denied, is BLOCKED before any handler runs
                     (fail closed). When None, no policy enforcement happens
                     (pre-V3.10 behavior preserved).
            tool_selections: V3.11 authoritative tool selections. When provided,
                     the executor runs exactly the validated tool + arguments
                     for each step; a missing or denied selection BLOCKS the
                     step before any handler runs (fail closed).

        Returns:
            ExecutionResult with per-step StepResults, accumulated outputs,
            and an overall status.
        """
        if not plan.steps:
            return ExecutionResult(
                status="completed",
                step_results=[],
                outputs={},
                final_output="No steps to execute.",
                error=None,
            )

        agent_state = getattr(context, "agent_state", None)

        # We iterate the steps as declared. V3.2 guarantees dependency ordering
        # (dependencies reference earlier step_ids). We still explicitly verify
        # readiness rather than assuming ordering.
        execution_order = sorted(plan.steps, key=lambda s: s.step_id)

        step_status: dict[int, str] = {}
        step_outputs: dict[int, str] = {}
        step_results: list[StepResult] = []

        for step in execution_order:
            result = self.execute_one(
                step,
                context=context,
                capability_selections=capability_selections,
                tool_selections=tool_selections,
                step_status=step_status,
                step_outputs=step_outputs,
            )
            step_status[step.step_id] = result.status
            if result.status == "completed":
                step_outputs[step.step_id] = result.output
            step_results.append(result)

        return build_execution_result(step_results, step_outputs)

    def execute_one(
        self,
        step: PlanStep,
        context: object = None,
        capability_selections: Optional[list[CapabilitySelection]] = None,
        tool_selections: Optional[list[ToolSelection]] = None,
        step_status: Optional[dict[int, str]] = None,
        step_outputs: Optional[dict[int, str]] = None,
    ) -> StepResult:
        """
        Execute a SINGLE plan step with full policy enforcement (V3.12).

        The V3.12 execution loop drives one eligible step per iteration through
        this method. All V3.10 capability enforcement and V3.11 tool selection
        enforcement is applied HERE — a loop, executor, or handler can never
        bypass it. Deterministic, no retries, no replanning.

        Args:
            step: The PlanStep to execute.
            context: The PipelineContext (optional). Provides user/session/project IDs.
            capability_selections: V3.10 authoritative capability selections.
            tool_selections: V3.11 authoritative tool selections.
            step_status: statuses of already-processed steps (for dependency checks).
            step_outputs: outputs of already-completed steps (for dependency context).

        Returns:
            StepResult: completed | failed | blocked.
        """
        step_status = step_status or {}
        step_outputs = step_outputs or {}
        agent_state = getattr(context, "agent_state", None)

        # V3.10: authoritative capability selections (last selection wins).
        capability_by_id: dict[int, CapabilitySelection] = {}
        if capability_selections is not None:
            capability_by_id = {s.step_id: s for s in capability_selections}

        # V3.11: authoritative tool selections (last selection wins).
        tool_by_id: dict[int, ToolSelection] = {}
        if tool_selections is not None:
            tool_by_id = {s.step_id: s for s in tool_selections}

        # ── Check if all dependencies have succeeded ───────────────────────
        for dep_id in step.dependencies:
            if step_status.get(dep_id) != "completed":
                return _blocked_result(
                    step,
                    f"Blocked: dependency step(s) {step.dependencies} did not complete successfully.",
                    agent_state,
                )

        # ── Capability policy enforcement (V3.10) ───────────────────────────
        # Selections are authoritative: a denied step — or a step with no
        # selection — must NEVER reach a handler or tool. Fail closed.
        if capability_selections is not None:
            selection = capability_by_id.get(step.step_id)
            if selection is None:
                return _blocked_result(
                    step,
                    f"Blocked: no capability selection for step {step.step_id}",
                    agent_state,
                )
            if not selection.allowed:
                reason = selection.reason or (
                    f"Blocked: capability selection denied for step {step.step_id}"
                )
                return _blocked_result(step, reason, agent_state)

        # ── Tool policy enforcement (V3.11) ──────────────────────────────────
        # The ToolSelector's validated tool + arguments are authoritative:
        # a step without a selection, or with a denied selection, never
        # reaches a handler. Fail closed.
        tool_selection: Optional[ToolSelection] = None
        if tool_selections is not None:
            tool_selection = tool_by_id.get(step.step_id)
            if tool_selection is None:
                return _blocked_result(
                    step,
                    f"Blocked: no tool selection for step {step.step_id}",
                    agent_state,
                )
            if not tool_selection.allowed:
                reason = tool_selection.reason or (
                    f"Blocked: tool selection denied for step {step.step_id}"
                )
                return _blocked_result(step, reason, agent_state)

        # ── Build dependency context string ──────────────────────────────────
        dep_context_parts = []
        for dep_id in step.dependencies:
            dep_out = step_outputs.get(dep_id, "")
            if dep_out:
                dep_context_parts.append(f"[Step {dep_id}]\n{dep_out}")
        dep_context = "\n\n".join(dep_context_parts)

        # ── Dispatch step to handler ─────────────────────────────────────────
        handler = _ACTION_HANDLERS.get(step.action)
        if handler is None:
            err_msg = f"Unknown action: '{step.action}'. No handler registered."
            logger.error(
                "executor step_id=%d status=failed reason=unknown_action action=%s",
                step.step_id,
                step.action,
            )
            if agent_state:
                mark_step_started(agent_state, step.step_id, tool=step.tool)
                mark_step_failed(agent_state, step.step_id, err_msg)
            return StepResult(
                step_id=step.step_id,
                status="failed",
                output="",
                error=err_msg,
                tool=step.tool,
            )

        logger.info(
            "executor step_id=%d action=%s tool=%s running",
            step.step_id,
            step.action,
            step.tool,
        )

        if agent_state:
            mark_step_started(agent_state, step.step_id, tool=step.tool)

        try:
            output = handler(step, dep_context, context, tool_selection)
            result = StepResult(
                step_id=step.step_id,
                status="completed",
                output=output,
                error=None,
                tool=step.tool,
            )
            logger.info(
                "executor step_id=%d action=%s status=completed output_len=%d",
                step.step_id,
                step.action,
                len(output),
            )
            if agent_state:
                mark_step_completed(agent_state, step.step_id, output)
        except Exception as exc:
            error_msg = str(exc)
            result = StepResult(
                step_id=step.step_id,
                status="failed",
                output="",
                error=error_msg,
                tool=step.tool,
            )
            logger.error(
                "executor step_id=%d action=%s status=failed error=%s",
                step.step_id,
                step.action,
                error_msg,
            )
            if agent_state:
                mark_step_failed(agent_state, step.step_id, error_msg)

        return result
