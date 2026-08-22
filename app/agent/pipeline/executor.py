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
   - V4.6: dependency context is structured (StepContext) — a step receives
     ONLY its declared dependencies' outputs, size-bounded with safe
     truncation; every propagated entry retains originating step_id +
     execution_id for synthesis and audit. Reuses Memory V2 + AgentState;
     no new memory system.
   - V4.7: every tool outcome crosses the standard ToolResult boundary
     (status completed|failed|blocked|empty|timeout + stable error_code).
     Tool implementations are untouched; normalization happens at the
     boundary. Step status semantics, dependency gating, and the
     no-retry/no-replan policy are all preserved.
   - V4.11: reliability gates at the execution boundary — idempotent
     replay of terminal results (never re-runs a settled step), cooperative
     cancellation (request → current step, nothing left running/pending),
     request-level timeout, and per-tool/per-step timeout re-labeling onto
     the existing TOOL_TIMEOUT code. These gates ORDER AFTER the V3.10/V3.11
     enforcement passes, so they can never bypass policy; a context without
     reliability attributes behaves exactly as before.

Step execution order:
  1. Build a dependency-aware execution queue.
  2. Execute each step only after all its declared dependencies have succeeded.
  3. If a dependency fails, mark dependants as BLOCKED (not executed).
  4. Pass accumulated dependency outputs as context into each step.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field, replace
from typing import Callable, Optional, Union

from app.agent.pipeline.planner import Plan, PlanStep
from app.agent.pipeline.capabilities import CapabilitySelection
from app.agent.pipeline.tool_selection import ToolSelection
from app.agent.pipeline.state import (
    mark_step_started,
    mark_step_completed,
    mark_step_failed,
    mark_step_blocked,
)
from app.agent.pipeline.step_context import StepContext, StepContextBuilder
from app.agent.pipeline.tool_result import (
    ToolResult,
    normalize_execution,
    normalize_exception,
)
from app.agent.pipeline.cost import TokenBudget
from app.agent.pipeline.trace import AgentTrace, record_trace
from app.agent.pipeline.security import (
    RULE_CAPABILITY_DENIED,
    RULE_TOOL_DENIED,
    SecurityFinding,
    record_security,
    sanitize_output,
    validate_tool_inputs,
)
from app.agent.pipeline.reliability import (
    REASON_REQUEST_CANCELLED,
    REASON_REQUEST_TIMED_OUT,
    REASON_STEP_TIMED_OUT,
    REASON_TOOL_TIMED_OUT,
    idempotency_of,
    is_cancel_requested,
    reliability_guard_of,
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
    # V4.6: structured dependency-scoped context that fed this step;
    # carries lineage (step_id + execution_id) for synthesis and audit.
    step_context: Optional[StepContext] = None
    # V4.7: standardized tool outcome (status + stable error_code).
    tool_result: Optional[ToolResult] = None


@dataclass
class ExecutionResult:
    status: str                         # completed | partial | failed | blocked
    step_results: list[StepResult] = field(default_factory=list)
    outputs: dict[int, str] = field(default_factory=dict)
    final_output: Optional[str] = None
    error: Optional[str] = None


# ── Action Handlers ───────────────────────────────────────────────────────────
# Each handler receives (step, context_str, pipeline_ctx, tool_selection) and
# returns a ToolResult (V4.7 boundary). Handlers MUST use existing
# tool_impls / tool_gate, not implement tools here. Handlers never raise on
# gate outcomes — normalization maps outcomes to stable error codes.
# A plain str return is also accepted (coerced to a completed ToolResult).

ActionHandler = Callable[
    [PlanStep, str, object, Optional[ToolSelection]],
    Union[str, ToolResult],
]


def _handle_memory(
    step: PlanStep,
    context: str,
    pipeline_ctx: object,
    tool_selection: Optional[ToolSelection] = None,
) -> ToolResult:
    """Route to the existing memory tool via tool_gate guardrail.

    Returns a normalized ToolResult — never raises on gate denial or
    failure; the stable error_code carries the outcome for the Agent.
    """
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
    return normalize_execution(execution, tool=tool)


def _handle_knowledge(
    step: PlanStep,
    context: str,
    pipeline_ctx: object,
    tool_selection: Optional[ToolSelection] = None,
) -> ToolResult:
    """Route to the existing RAG knowledge base via tool_gate (project-scoped)."""
    p_context = getattr(pipeline_ctx, "context", None)
    if p_context and p_context.knowledge_context:
        return ToolResult(
            status="completed",
            tool=(tool_selection.tool if tool_selection else None) or "search_knowledge_base",
            output=p_context.knowledge_context,
        )

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
    return normalize_execution(execution, tool=tool)


def _handle_document(
    step: PlanStep,
    context: str,
    pipeline_ctx: object,
    tool_selection: Optional[ToolSelection] = None,
) -> ToolResult:
    """Document retrieval — same as knowledge, scoped to uploaded documents."""
    p_context = getattr(pipeline_ctx, "context", None)
    if p_context and p_context.document_context:
        return ToolResult(
            status="completed",
            tool=(tool_selection.tool if tool_selection else None) or "search_documents",
            output=p_context.document_context,
        )
    return _handle_knowledge(step, context, pipeline_ctx, tool_selection)


def _handle_web_search(
    step: PlanStep,
    context: str,
    pipeline_ctx: object,
    tool_selection: Optional[ToolSelection] = None,
) -> ToolResult:
    """Route to the existing Tavily web search via tool_gate."""
    p_context = getattr(pipeline_ctx, "context", None)
    if p_context and p_context.web_context:
        return ToolResult(
            status="completed",
            tool=(tool_selection.tool if tool_selection else None) or "web_search",
            output=p_context.web_context,
        )

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
    return normalize_execution(execution, tool=tool)


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
    text = str(content).strip()

    # ── V4.9: capture provider/model usage at the boundary ──────────────────
    # The executor pops this from ToolResult.metadata and records it into the
    # TokenBudget (per-step + per-request accounting). When the provider
    # reports no usage metadata, the plain-str legacy return is preserved.
    usage: dict = {}
    usage_meta = getattr(response, "usage_metadata", None)
    if isinstance(usage_meta, dict):
        usage["input_tokens"] = int(usage_meta.get("input_tokens", 0) or 0)
        usage["output_tokens"] = int(usage_meta.get("output_tokens", 0) or 0)
    model = getattr(llm, "model_name", "")
    if isinstance(model, str) and model:
        usage["model"] = model
    if usage:
        return ToolResult(
            status="completed",
            tool=step.tool or "",
            output=text,
            metadata={"token_usage": usage},
        )
    return text


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

def _blocked_result(
    step: PlanStep,
    reason: str,
    agent_state: object,
    trace_context: object = None,
    security_rule: Optional[str] = None,
) -> StepResult:
    """Build a blocked StepResult without executing the step's handler.

    V4.10: when security_rule is set (capability/tool authorization
    denial), the decision is ALSO recorded as a security_blocked event
    on the existing AgentTrace — authorization is enforced by the
    V3.10/V3.11 layers; this only makes the decision observable.
    """
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
    record_trace(
        trace_context, "execution", "step_blocked",
        status="blocked", step_id=step.step_id, tool=step.tool or "",
    )
    if security_rule is not None:
        record_security(
            trace_context, "blocked",
            [SecurityFinding(rule=security_rule, source="authorization", count=1)],
            tool=step.tool or "", step_id=step.step_id,
        )
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

        # V4.11: reliability plumbing (defensive — plain contexts and
        # MagicMock-based contexts behave exactly as before V4.11).
        guard = reliability_guard_of(context)
        ledger = idempotency_of(context)
        execution_id = getattr(context, "execution_id", "") or ""
        if not execution_id and agent_state:
            execution_id = getattr(agent_state, "request_id", "") or ""

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
                    trace_context=context,
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
                    trace_context=context,
                    security_rule=RULE_CAPABILITY_DENIED,
                )
            if not selection.allowed:
                reason = selection.reason or (
                    f"Blocked: capability selection denied for step {step.step_id}"
                )
                return _blocked_result(
                    step, reason, agent_state, trace_context=context,
                    security_rule=RULE_CAPABILITY_DENIED,
                )

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
                    trace_context=context,
                    security_rule=RULE_TOOL_DENIED,
                )
            if not tool_selection.allowed:
                reason = tool_selection.reason or (
                    f"Blocked: tool selection denied for step {step.step_id}"
                )
                return _blocked_result(
                    step, reason, agent_state, trace_context=context,
                    security_rule=RULE_TOOL_DENIED,
                )

        # ── V4.11: idempotent replay (AFTER all enforcement passes) ────────
        # A terminal result for this (execution_id, step_id) is replayed
        # instead of running the handler again — first terminal result
        # wins and is never overwritten. Checked only after the V3.10/V3.11
        # enforcement passes, so replay can never bypass policy.
        if ledger is not None:
            cached = ledger.terminal_for(execution_id, step.step_id)
            if cached is not None:
                logger.info(
                    "executor_step_replayed step_id=%d status=%s",
                    step.step_id, cached.status,
                )
                return StepResult(
                    step_id=cached.step_id,
                    status=cached.status,
                    output=cached.output,
                    error=cached.error,
                    tool=cached.tool,
                    tool_result=(
                        ToolResult(**cached.tool_result)
                        if cached.tool_result is not None else None
                    ),
                )

        # ── V4.11: cooperative cancellation (request → current step) ──────
        # The operator's intent wins: a cancelled request never starts a
        # new handler. The step is marked blocked so nothing is left
        # running or pending.
        if is_cancel_requested(context):
            logger.info(
                "executor step_id=%d status=blocked reason=request_cancelled",
                step.step_id,
            )
            if agent_state:
                mark_step_blocked(agent_state, step.step_id, REASON_REQUEST_CANCELLED)
            record_trace(
                context, "execution", "step_cancelled",
                status="blocked", step_id=step.step_id, tool=step.tool or "",
            )
            return StepResult(
                step_id=step.step_id,
                status="blocked",
                output="",
                error=REASON_REQUEST_CANCELLED,
                tool=step.tool,
            )

        # ── V4.11: request-level timeout (before any handler runs) ────────
        if guard is not None and guard.request_expired():
            logger.info(
                "executor step_id=%d status=blocked reason=request_timed_out",
                step.step_id,
            )
            if agent_state:
                mark_step_blocked(agent_state, step.step_id, REASON_REQUEST_TIMED_OUT)
            record_trace(
                context, "execution", "step_blocked",
                status="blocked", step_id=step.step_id, tool=step.tool or "",
                metadata={"reason": REASON_REQUEST_TIMED_OUT},
            )
            return StepResult(
                step_id=step.step_id,
                status="blocked",
                output="",
                error=REASON_REQUEST_TIMED_OUT,
                tool=step.tool,
            )

        # ── V4.9: Token budget enforcement (BEFORE any LLM call) ────────────
        # A TokenBudget gates this step when the request budget or the
        # per-step budget is exhausted: the handler NEVER runs, so no LLM
        # call happens (runaway multi-step prevention). Passive — a
        # context without a budget behaves exactly as before V4.9.
        budget = getattr(context, "token_budget", None)
        if isinstance(budget, TokenBudget):
            budget_reason = budget.check(step_id=step.step_id)
            if budget_reason:
                logger.warning(
                    "executor step_id=%d status=blocked reason=%s",
                    step.step_id,
                    budget_reason,
                )
                if agent_state:
                    mark_step_blocked(agent_state, step.step_id, budget_reason)
                record_trace(
                    context, "execution", "step_blocked",
                    status="blocked", step_id=step.step_id, tool=step.tool or "",
                    metadata={"reason": budget_reason},
                )
                return StepResult(
                    step_id=step.step_id,
                    status="blocked",
                    output="",
                    error=budget_reason,
                    tool=step.tool,
                )

        # ── V4.10: tool INPUT boundary (before any handler/tool runs) ──────
        # Validates the authoritative V3.11 arguments: non-scalar values
        # BLOCK the step (fail closed, before any tool call); secrets/PII
        # in scalar values are redacted before the handler sees them and
        # the decision is recorded on the existing AgentTrace.
        if tool_selection is not None and tool_selection.arguments:
            clean_args, input_findings, blocked_input = validate_tool_inputs(
                tool_selection.tool or step.tool or "",
                tool_selection.arguments,
            )
            if blocked_input:
                logger.warning(
                    "executor step_id=%d status=blocked reason=invalid_tool_input tool=%s",
                    step.step_id, tool_selection.tool or step.tool,
                )
                if agent_state:
                    mark_step_blocked(
                        agent_state, step.step_id,
                        "Tool input invalid: non-scalar argument value.",
                    )
                record_security(
                    context, "blocked", input_findings,
                    tool=tool_selection.tool or step.tool or "",
                    step_id=step.step_id,
                )
                return StepResult(
                    step_id=step.step_id,
                    status="blocked",
                    output="",
                    error="Tool input invalid: non-scalar argument value.",
                    tool=step.tool,
                )
            if input_findings:
                tool_selection = replace(tool_selection, arguments=clean_args)
                record_security(
                    context, "flag", input_findings,
                    tool=tool_selection.tool or step.tool or "",
                    step_id=step.step_id,
                )

        # ── V4.6: Build structured, dependency-scoped execution context ─────
        # The step receives ONLY outputs of its DECLARED dependencies, in
        # declared order. Size-bounded with safe truncation; every entry
        # retains its originating step_id + execution_id. The rendered
        # plain text keeps the exact V3.3 wire format so handlers are
        # unchanged.
        step_ctx = StepContextBuilder().build(
            step=step,
            step_outputs=step_outputs,
            request_id=getattr(agent_state, "request_id", "") if agent_state else "",
            execution_id=getattr(context, "execution_id", "") or "",
            session_id=getattr(context, "session_id", "") if context else "",
            project_id=getattr(context, "project_id", "") if context else "",
            step_status=step_status,
        )
        dep_context = step_ctx.to_plain_text()

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
        record_trace(
            context, "execution", "step_started",
            step_id=step.step_id, tool=step.tool or "",
        )

        execution_id = getattr(context, "execution_id", "") or ""
        if not execution_id and agent_state:
            execution_id = getattr(agent_state, "request_id", "") or ""

        # V4.11: time starts on the guard's injectable clock (deterministic
        # timeout tests); otherwise the monotonic clock as before.
        t0 = guard.now() if guard is not None else time.monotonic()

        # ── V4.7: handler -> ToolResult boundary ─────────────────────────────
        # Handlers return normalized ToolResults. Exceptions are normalized
        # into stable error codes (never raw provider text as primary error).
        # Plain str returns (legacy/crafted handlers) coerce to completed.
        try:
            raw = handler(step, dep_context, context, tool_selection)
        except Exception as exc:
            tr = normalize_exception(exc, tool=step.tool or "")
            logger.error(
                "executor step_id=%d action=%s status=%s error_code=%s error=%s",
                step.step_id,
                step.action,
                tr.status,
                tr.error_code,
                str(exc)[:200],
            )
        else:
            if isinstance(raw, ToolResult):
                tr = raw
            elif isinstance(raw, str):
                tr = ToolResult(status="completed", tool=step.tool or "", output=raw)
            else:
                tr = ToolResult(
                    status="failed",
                    tool=step.tool or "",
                    error_code="TOOL_FAILED",
                    error=(
                        "Tool returned malformed output "
                        f"(type={type(raw).__name__}, not str or ToolResult)."
                    ),
                )
                logger.error(
                    "executor step_id=%d action=%s status=failed reason=malformed_output",
                    step.step_id,
                    step.action,
                )

        now = guard.now() if guard is not None else time.monotonic()
        latency_ms = round((now - t0) * 1000, 2)
        tr = replace(
            tr,
            step_id=step.step_id,
            execution_id=execution_id,
            latency_ms=latency_ms,
        )

        # ── V4.11: timeout boundaries (tool first, then step) ─────────────
        # A long-running handler is re-labeled timeout with the EXISTING
        # TOOL_TIMEOUT code — nothing new enters the taxonomy, and the
        # timeout → failed step mapping below already exists. A timed-out
        # tool produced no usable output (matches normalize_execution's
        # timeout branch). A fast provider-side timeout (normalized at the
        # boundary) is untouched.
        if guard is not None:
            if guard.tool_exceeded(t0):
                tr = replace(tr, status="timeout", error_code="TOOL_TIMEOUT",
                             error=REASON_TOOL_TIMED_OUT, output="")
            elif guard.step_exceeded(t0):
                tr = replace(tr, status="timeout", error_code="TOOL_TIMEOUT",
                             error=REASON_STEP_TIMED_OUT, output="")

        # ── V4.9: per-step + per-request token accounting ───────────────────
        # Handlers report provider usage via ToolResult.metadata
        # ["token_usage"] (popped here so the ToolResult boundary stays
        # clean). The budget records it under this step and the request;
        # trace events carry only derived, non-sensitive numbers.
        usage: Optional[dict] = None
        if isinstance(tr.metadata, dict):
            # replace() — the boundary artifact is never mutated in place.
            usage = tr.metadata.get("token_usage")
            if usage is not None:
                tr = replace(
                    tr,
                    metadata={k: v for k, v in tr.metadata.items() if k != "token_usage"},
                )
        cost_meta: dict = {}
        if isinstance(budget, TokenBudget) and isinstance(usage, dict):
            model = str(usage.get("model", "") or "")
            t_in = int(usage.get("input_tokens", 0) or 0)
            t_out = int(usage.get("output_tokens", 0) or 0)
            budget.record(
                model=model, input_tokens=t_in, output_tokens=t_out,
                step_id=step.step_id,
            )
            cost_meta = {
                "model": model,
                "usage_in": t_in,
                "usage_out": t_out,
                "cost_usd": round(budget.estimate_cost(model, t_in, t_out), 6),
            }

        # ── V4.10: tool OUTPUT boundary ────────────────────────────────────
        # Secrets/PII are redacted from every step output before it can
        # reach a downstream step, synthesis, or the LLM. Injection markers
        # in outputs are FLAGGED only — agent-generated text is never
        # silently rewritten (it is not untrusted retrieved content).
        if isinstance(tr.output, str) and tr.output:
            safe_output, out_findings = sanitize_output(tr.output)
            if out_findings:
                tr = replace(tr, output=safe_output)
                record_security(
                    context, "flag", out_findings,
                    tool=tr.tool or step.tool or "", step_id=step.step_id,
                )

        # ── Map ToolResult onto preserved step status semantics ─────────────
        # completed / empty  -> StepResult 'completed' (empty carries the
        #   structured 'empty' signal for synthesis/validation)
        # blocked             -> StepResult 'blocked' (did not execute)
        # failed / timeout    -> StepResult 'failed'
        if tr.status in ("completed", "empty"):
            result = StepResult(
                step_id=step.step_id,
                status="completed",
                output=tr.output,
                error=None,
                tool=step.tool,
                step_context=step_ctx,
                tool_result=tr,
            )
            logger.info(
                "executor step_id=%d action=%s status=completed tool_status=%s output_len=%d",
                step.step_id,
                step.action,
                tr.status,
                len(tr.output),
            )
            if agent_state:
                mark_step_completed(agent_state, step.step_id, tr.output)
            record_trace(
                context, "execution", "step_completed",
                status="completed", step_id=step.step_id, tool=step.tool or "",
                duration_ms=latency_ms,
            )
            record_trace(
                context, "execution", AgentTrace.tool_event_for(tr.status),
                status=tr.status, step_id=step.step_id, tool=tr.tool or step.tool or "",
                duration_ms=latency_ms,
                metadata={"error_code": tr.error_code, **cost_meta},
            )
        elif tr.status == "blocked":
            blk_reason = f"{tr.error_code}: {tr.error}" if tr.error_code else "Tool blocked."
            result = StepResult(
                step_id=step.step_id,
                status="blocked",
                output="",
                error=blk_reason,
                tool=step.tool,
                step_context=step_ctx,
                tool_result=tr,
            )
            logger.warning(
                "executor step_id=%d action=%s status=blocked error_code=%s",
                step.step_id,
                step.action,
                tr.error_code,
            )
            if agent_state:
                mark_step_blocked(agent_state, step.step_id, blk_reason)
            record_trace(
                context, "execution", "step_blocked",
                status="blocked", step_id=step.step_id, tool=step.tool or "",
                duration_ms=latency_ms,
            )
            record_trace(
                context, "execution", "tool_blocked",
                status=tr.status, step_id=step.step_id, tool=tr.tool or step.tool or "",
                duration_ms=latency_ms,
                metadata={"error_code": tr.error_code, **cost_meta},
            )
        else:
            result = StepResult(
                step_id=step.step_id,
                status="failed",
                output="",
                error=tr.error or tr.error_code or "Tool failed.",
                tool=step.tool,
                step_context=step_ctx,
                tool_result=tr,
            )
            logger.error(
                "executor step_id=%d action=%s status=failed error_code=%s",
                step.step_id,
                step.action,
                tr.error_code,
            )
            if agent_state:
                mark_step_failed(
                    agent_state, step.step_id, tr.error or tr.error_code or "Tool failed."
                )
            record_trace(
                context, "execution", "step_failed",
                status="failed", step_id=step.step_id, tool=step.tool or "",
                duration_ms=latency_ms,
            )
            record_trace(
                context, "execution", "tool_failed",
                status=tr.status, step_id=step.step_id, tool=tr.tool or step.tool or "",
                duration_ms=latency_ms,
                metadata={"error_code": tr.error_code, **cost_meta},
            )

        # V4.11: settle this terminal outcome in the ledger (first wins;
        # non-terminal statuses are never cached).
        if ledger is not None:
            ledger.record(execution_id, step.step_id, result)

        return result
