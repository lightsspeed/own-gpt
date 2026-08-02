"""Tool gate — the single guarded entry point for every agent tool call.

Pipeline (per the roadmap):
    LLM Tool Request -> Guardrail -> [HITL Approval if Mutating] -> Sandboxed Execution -> Record

Read-only calls execute immediately in-process (they have no side effects).
Mutating calls are recorded as pending and return a message to the agent;
a human operator approves them via the operations API, which triggers the
sandboxed execution. Every call is persisted as a ToolExecution artifact.
"""

from __future__ import annotations

import logging

from app.agent.guardrail import check_tool_call, GuardrailAction
from app.agent import tool_impls
from app.learning.operations.tool_execution import ToolExecution, ToolExecutionStore

logger = logging.getLogger(__name__)

# module-name → core implementation for sandboxed execution by name
IMPL_MODULE = "app.agent.tool_impls"
IMPL_FUNCS = {
    "search_knowledge_base": "search_knowledge_base_impl",
    "sm_integration": "sm_integration_impl",
    "remember_user_fact": "remember_user_fact_impl",
}

# Mutating tools run sandboxed; read-only tools run in-process.
MUTATING_TOOLS = frozenset({"sm_integration", "remember_user_fact"})


def _record(store: ToolExecutionStore, tool_name: str, args: dict, **kwargs) -> ToolExecution:
    execution = ToolExecution(tool_name=tool_name, args=args, **kwargs)
    return store.save(execution)


def _run_in_process(execution: ToolExecution, store: ToolExecutionStore) -> ToolExecution:
    """Execute a read-only tool in-process (safe, no side effects)."""
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
