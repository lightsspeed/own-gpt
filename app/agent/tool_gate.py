"""Tool gate — the single guarded entry point for every agent tool call.

Flow:
    LLM Tool Request -> Guardrail -> [Sandboxed Execution] -> Record

  - Read-only tools and low-risk memory tools execute immediately in-process
    (auto-applied chat personalization; every call is recorded as a
    ToolExecution artifact for audit).
  - Mutating side-effect tools are recorded as pending; a human operator
    approves via the operations API, which triggers sandboxed execution.
"""

from __future__ import annotations

import logging

from app.agent.guardrail import check_tool_call, GuardrailAction
from app.agent import tool_impls
from app.learning.operations.tool_execution import ToolExecution, ToolExecutionStore
from app.core import metrics as core_metrics

logger = logging.getLogger(__name__)

# module-name → core implementation for sandboxed execution by name
IMPL_MODULE = "app.agent.tool_impls"
IMPL_FUNCS = {
    "search_knowledge_base": "search_knowledge_base_impl",
    "web_search": "web_search_impl",
    "sm_integration": "sm_integration_impl",
    "remember_user_fact": "remember_user_fact_impl",
    "remember_session_fact": "remember_session_fact_impl",
    "forget_user_fact": "forget_user_fact_impl",
}

# Mutating side-effect tools run sandboxed after human approval; read-only
# and low-risk memory tools run in-process (auto-applied).
MUTATING_TOOLS = frozenset({"sm_integration"})


def _record(store: ToolExecutionStore, tool_name: str, args: dict, **kwargs) -> ToolExecution:
    execution = ToolExecution(tool_name=tool_name, args=args, **kwargs)
    return store.save(execution)


# ── Tool metrics (recorded at this guarded boundary — the ONLY tool boundary) ─
# Every tool call in the system passes through request_tool_execution (agent
# graph, executor) or execute_approved (post-approval). Recording here gives
# one accurate view of tool outcomes; metrics never duplicate each other.

def _observe_execution(execution: ToolExecution) -> None:
    """Record one TERMINAL tool execution into the agent tool metrics.

    Mapping (gate status → metric status):
      executed  → tool_calls_total{completed} + duration
      failed    → tool_calls_total{failed} + failures{error_code}
      timed_out → tool_calls_total{failed} + failures{sandbox_timed_out}
    `sandboxed` distinguishes the sandbox path (approval flow) from an
    in-process run. Approval-"pending" calls are NOT recorded here — they are
    counted when they terminate after approval (single accounting per call).
    """
    tool = core_metrics.bounded_tool(execution.tool_name)
    status = execution.status
    if status == "executed":
        core_metrics.safe_agent_count("tool_calls_total", tool=tool, status="completed")
        duration_s = max(float(getattr(execution, "duration_ms", 0) or 0), 0) / 1000.0
        core_metrics.safe_agent_observe("tool_duration_seconds", duration_s, tool=tool)
    elif status in ("failed", "timed_out"):
        if status == "timed_out":
            code = "sandbox_timed_out"
        elif execution.tool_name not in IMPL_FUNCS:
            code = "unregistered_impl"
        elif getattr(execution, "sandboxed", False):
            code = "sandbox_failed"
        else:
            code = "execution_failed"
        core_metrics.safe_agent_count("tool_calls_total", tool=tool, status="failed")
        core_metrics.safe_agent_count("tool_failures_total", tool=tool, error_code=code)


def _observe_denied(execution: ToolExecution, reason: str) -> None:
    """Record a guardrail-denied call (blocked before anything ran)."""
    tool = core_metrics.bounded_tool(execution.tool_name)
    core_metrics.safe_agent_count("tool_calls_total", tool=tool, status="blocked")
    core_metrics.safe_agent_count(
        "tool_blocked_total", tool=tool, reason=_block_reason_code(reason)
    )


def _block_reason_code(reason: str) -> str:
    """Map the deterministic guardrail reason to the bounded reason taxonomy.

    Guardrail reasons can embed user-shaped values (e.g. an offending
    target/action); the CODE is always a member of the finite taxonomy in
    app/core/metrics.py so Prometheus cardinality stays bounded.
    """
    r = (reason or "").lower()
    if "not registered" in r:
        return "unregistered_tool"
    if "deny-listed" in r:
        return "deny_listed"
    if "exceeds 500" in r:
        return "fact_too_long"
    if "must not be empty" in r:
        return "empty_fact"
    if "credentials or secrets" in r:
        return "secret_content"
    if "exceeds 128" in r:
        return "session_too_long"
    if "target" in r:
        return "invalid_target"
    if "action" in r:
        return "invalid_action"
    if "approval" in r:
        return "approval_required"
    return "unknown"


def _run_in_process(execution: ToolExecution, store: ToolExecutionStore) -> ToolExecution:
    """Execute an allowed tool in-process (read-only or low-risk memory write)."""
    import time
    fn_name = IMPL_FUNCS.get(execution.tool_name)
    start = time.perf_counter()
    try:
        fn = getattr(tool_impls, fn_name)
        result = fn(**execution.args)
        execution.duration_ms = (time.perf_counter() - start) * 1000
        execution.result = result
        execution.sandboxed = False
        execution.append_event("executed", note="read-only tool ran in-process")
        execution.status = "executed"
    except Exception as e:  # noqa: BLE001
        logger.exception("In-process tool execution failed for %s", execution.tool_name)
        execution.duration_ms = (time.perf_counter() - start) * 1000
        execution.error = str(e)
        execution.append_event("failed", note=str(e))
        execution.status = "failed"
    _observe_execution(execution)
    return store.save(execution)


def request_tool_execution(tool_name: str, args: dict) -> ToolExecution:
    """Route a tool call through the gate. Returns the recorded execution.

    This is the function the agent graph calls for every tool request.
    """
    store = ToolExecutionStore()
    decision = check_tool_call(tool_name, args or {})

    if decision.action == GuardrailAction.DENY:
        execution = _record(store, tool_name, args or {})
        execution.append_event("denied", note=decision.reason)
        execution.status = "denied"
        execution.error = decision.reason
        _observe_denied(execution, decision.reason)
        return store.save(execution)

    if decision.action == GuardrailAction.ALLOW:
        execution = _record(store, tool_name, args or {})
        execution.append_event("allowed", note=decision.reason)
        execution.status = "allowed"
        execution = _run_in_process(execution, store)
        return execution

    # REQUIRE_APPROVAL — mutating tool waits for a human operator
    execution = _record(store, tool_name, args or {})
    execution.append_event("pending", note=decision.reason)
    return store.save(execution)


def execute_approved(execution: ToolExecution) -> dict:
    """Run a pending mutating tool in the sandbox (called by the approval endpoint).

    Transitions the SAME recorded artifact pending -> approved -> executed/failed,
    preserving lineage. Never executes on its own — the operator already approved.
    """
    store = ToolExecutionStore()
    execution.append_event("approved", note="operator approved execution")
    execution.status = "approved"

    from app.agent.sandbox import run_sandboxed

    fn_name = IMPL_FUNCS.get(execution.tool_name)
    if not fn_name:
        execution.error = f"No implementation registered for {execution.tool_name}"
        execution.append_event("failed", note=execution.error)
        execution.status = "failed"
        _observe_execution(execution)
        store.save(execution)
        return {"ok": False, "error": execution.error, "id": execution.id}

    result = run_sandboxed(IMPL_MODULE, fn_name, kwargs=execution.args)
    execution.duration_ms = result.duration_ms
    execution.sandboxed = True
    if result.ok:
        execution.result = result.output
        execution.append_event("executed", note="sandboxed execution succeeded")
        execution.status = "executed"
    elif result.timed_out:
        execution.error = result.error
        execution.append_event("timed_out", note=result.error)
        execution.status = "timed_out"
    else:
        execution.error = result.error
        execution.append_event("failed", note=result.error or "sandbox execution failed")
        execution.status = "failed"

    _observe_execution(execution)
    store.save(execution)
    return {
        "ok": result.ok,
        "id": execution.id,
        "tool_name": execution.tool_name,
        "result": execution.result,
        "error": execution.error,
        "duration_ms": execution.duration_ms,
        "sandboxed": True,
    }
