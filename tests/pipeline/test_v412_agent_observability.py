"""Phase 3.2 / V4.12 — agent observability metrics (hermetic tests).

Covers:
  - the eight owngpt_agent_* metric families are registered and rendered
  - request metrics are recorded at the SINGLE finalization boundary
    (finalize_trace) exactly once, from the same status that lands on the
    request_completed trace event and the same shared TokenBudget totals
  - status vocabulary: completed/partial/failed/blocked/cancelled/timed_out
    (validation-failure downgrade + explicit override)
  - tool metrics are recorded at the single guarded gate
    (request_tool_execution / execute_approved) with bounded error codes and
    block reasons; approval-pending calls are counted once, with their real
    terminal outcome
  - model/tool labels collapse to allowlists plus "other"
  - cardinality: no user/session/request/execution IDs anywhere in output
  - fail-open: a broken metrics registry can never break finalize or the gate

Zero live pipeline / API / DB / LLM / network calls.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from prometheus_client import CollectorRegistry, generate_latest

from app.agent.pipeline.cost import TokenBudget
from app.agent.pipeline.trace import AgentTrace
from app.learning.operations.tool_execution import ToolExecution
from app.core import metrics as core_metrics


class EmptyStore:
    def similarity_search_with_score(self, *a, **k):
        return []


@pytest.fixture
def pipeline():
    from app.agent.pipeline.pipeline import RAGPipeline

    return RAGPipeline(
        vector_store=EmptyStore(),
        redis_url=None,
        config={
            "intent_enabled": False,
            "rewrite_enabled": False,
            "learning_enabled": False,
            "trace_enabled": False,
            "answer_validation_use_llm": False,
        },
    )


@pytest.fixture
def ctx():
    from app.agent.pipeline.pipeline import PipelineContext

    ctx = PipelineContext(question="q", session_id="session-1", project_id="p-1")
    ctx.agent_trace = AgentTrace(
        request_id="req-1", execution_id="exe-1",
        session_id="session-1", project_id="p-1",
    )
    ctx.token_budget = TokenBudget()
    return ctx


@pytest.fixture
def fresh_agent_metrics(monkeypatch):
    fresh = core_metrics.AgentMetrics(CollectorRegistry())
    monkeypatch.setattr(core_metrics, "agent_metrics", fresh)
    return fresh


def _body(fresh) -> str:
    return generate_latest(fresh.registry).decode()


def _completed(ctx):
    return [e for e in ctx.agent_trace.events() if e.event == "request_completed"]


# ── Registry & cardinality ───────────────────────────────────────────────────

class TestRegistry:
    def test_agent_families_registered(self):
        names = core_metrics.registered_metric_names()
        for name in (
            "owngpt_agent_requests_total",
            "owngpt_agent_request_tokens_total",
            "owngpt_agent_request_cost_usd_total",
            "owngpt_agent_tool_calls_total",
            "owngpt_agent_tool_failures_total",
            "owngpt_agent_tool_blocked_total",
        ):
            assert name in names
        for metric in ("owngpt_agent_request_duration_seconds",
                       "owngpt_agent_tool_duration_seconds"):
            for suffix in ("_bucket", "_sum", "_count"):
                assert f"{metric}{suffix}" in names

    def test_render_metrics_includes_agent_registry(self, monkeypatch):
        fresh = core_metrics.AgentMetrics(CollectorRegistry())
        monkeypatch.setattr(core_metrics, "agent_metrics", fresh)
        body = core_metrics.render_metrics().decode()
        assert "owngpt_agent" in body

    def test_no_forbidden_identifiers_anywhere_in_agent_output(
        self, pipeline, ctx, fresh_agent_metrics
    ):
        ctx.agent_state = SimpleNamespace(cancelled=False, request_timed_out=True)
        ctx.token_budget.record("gpt-4o-mini", 100, 50)
        pipeline.finalize_trace(ctx)
        body = _body(fresh_agent_metrics)
        for forbidden in (
            "user_id", "user_hash", "session_id", "conversation_id", "message_id",
            "request_id", "run_id", "execution_id", "memory_id",
        ):
            assert forbidden not in body

    def test_label_validation_is_strict_except_model_tool(self):
        m = core_metrics.AgentMetrics(CollectorRegistry())
        with pytest.raises(ValueError):
            m.validate("status", "mystery")
        m.validate("status", "cancelled")
        with pytest.raises(ValueError):
            m.validate("error_code", "raw exception text here")
        # Bounded non-raised labels.
        assert m.validate("tool", "mystery_tool") == "other"
        assert m.validate("tool", "web_search") == "web_search"
        assert m.validate("model", "totally-unknown-model") == "other"


# ── Request metrics: single finalization boundary ────────────────────────────

class TestFinalizeRequestMetrics:
    def test_records_status_duration_and_budget_totals_once(
        self, pipeline, ctx, fresh_agent_metrics
    ):
        ctx.token_budget.record("gpt-4o-mini", 1000, 500)
        ctx.token_budget.record("deepseek-chat", 200, 100)
        pipeline.finalize_trace(ctx)

        body = _body(fresh_agent_metrics)
        assert 'owngpt_agent_requests_total{status="completed"} 1.0' in body
        assert 'owngpt_agent_request_tokens_total{model="gpt-4o-mini"} 1500.0' in body
        # deepseek-chat is not in the config allowlist → bounded to "other".
        assert 'owngpt_agent_request_tokens_total{model="other"} 300.0' in body
        # gpt-4o-mini: 1000/1e6*0.15 + 500/1e6*0.60 = 0.00045
        assert 'owngpt_agent_request_cost_usd_total{model="gpt-4o-mini"} 0.00045' in body
        assert 'owngpt_agent_request_duration_seconds_count 1.0' in body
        # The trace event carries the SAME status derived from the same facts.
        assert _completed(ctx)[0].status == "completed"

    def test_multiple_finalize_calls_record_metrics_once(
        self, pipeline, ctx, fresh_agent_metrics
    ):
        pipeline.finalize_trace(ctx)
        pipeline.finalize_trace(ctx)
        pipeline.finalize_trace(ctx, status="failed")  # late retry path
        body = _body(fresh_agent_metrics)
        assert 'owngpt_agent_requests_total{status="completed"} 1.0' in body
        assert 'owngpt_agent_requests_total{status="failed"} ' not in _body(fresh_agent_metrics)
        assert 'owngpt_agent_request_duration_seconds_count 1.0' in body

    def test_cancelled_status_and_trace_agree(self, pipeline, ctx, fresh_agent_metrics):
        ctx.agent_state = SimpleNamespace(cancelled=True, request_timed_out=False)
        pipeline.finalize_trace(ctx)
        assert 'owngpt_agent_request_duration_seconds_count 1.0' in _body(fresh_agent_metrics)
        assert 'owngpt_agent_requests_total{status="cancelled"} 1.0' in _body(fresh_agent_metrics)
        assert _completed(ctx)[0].status == "cancelled"

    def test_timed_out_status(self, pipeline, ctx, fresh_agent_metrics):
        ctx.agent_state = SimpleNamespace(cancelled=False, request_timed_out=True)
        pipeline.finalize_trace(ctx)
        assert 'owngpt_agent_requests_total{status="timed_out"} 1.0' in _body(fresh_agent_metrics)
        assert _completed(ctx)[0].status == "timed_out"

    def test_cancellation_wins_over_timeout(self, pipeline, ctx, fresh_agent_metrics):
        ctx.agent_state = SimpleNamespace(cancelled=True, request_timed_out=True)
        pipeline.finalize_trace(ctx)
        assert 'owngpt_agent_requests_total{status="cancelled"} 1.0' in _body(fresh_agent_metrics)

    def test_partial_execution_status(self, pipeline, ctx, fresh_agent_metrics):
        ctx.execution = SimpleNamespace(status="partial")
        pipeline.finalize_trace(ctx)
        assert 'owngpt_agent_requests_total{status="partial"} 1.0' in _body(fresh_agent_metrics)

    def test_validation_failure_downgrades_status(self, pipeline, ctx, fresh_agent_metrics):
        ctx.validation = SimpleNamespace(valid=False)
        pipeline.finalize_trace(ctx)
        assert 'owngpt_agent_requests_total{status="failed"} 1.0' in _body(fresh_agent_metrics)
        assert _completed(ctx)[0].status == "failed"

    def test_unknown_model_collapses_to_other(self, pipeline, ctx, fresh_agent_metrics):
        ctx.token_budget.record("mystery-model", 100, 50)
        pipeline.finalize_trace(ctx)
        assert 'owngpt_agent_request_tokens_total{model="other"} 150.0' in _body(fresh_agent_metrics)
        assert "mystery-model" not in _body(fresh_agent_metrics)

    def test_fail_open_broken_registry_never_breaks_finalize(
        self, pipeline, ctx, monkeypatch
    ):
        class BrokenMetrics:
            def count(self, *a, **k):
                raise RuntimeError("registry broken")

            def observe(self, *a, **k):
                raise RuntimeError("registry broken")

        monkeypatch.setattr(core_metrics, "agent_metrics", BrokenMetrics())
        pipeline.finalize_trace(ctx)  # must not raise
        assert _completed(ctx)[0].status == "completed"


# ── Tool metrics: the single guarded gate ────────────────────────────────────

class _NoopStore:
    def save(self, execution):
        return execution


@pytest.fixture
def gate_store(monkeypatch):
    monkeypatch.setattr("app.agent.tool_gate.ToolExecutionStore", lambda: _NoopStore())


@pytest.fixture
def fresh_gate_metrics(monkeypatch):
    fresh = core_metrics.AgentMetrics(CollectorRegistry())
    monkeypatch.setattr(core_metrics, "agent_metrics", fresh)
    return fresh


class TestToolGateMetrics:
    def test_executed_in_process_records_completed_and_duration(
        self, monkeypatch, gate_store, fresh_gate_metrics
    ):
        monkeypatch.setattr(
            "app.agent.tool_impls.web_search_impl", lambda **k: "ok"
        )
        from app.agent.tool_gate import request_tool_execution

        execution = request_tool_execution("web_search", {"query": "q"})
        assert execution.status == "executed"

        body = _body(fresh_gate_metrics)
        assert 'owngpt_agent_tool_calls_total{status="completed",tool="web_search"} 1.0' in body
        assert 'owngpt_agent_tool_duration_seconds_count{tool="web_search"} 1.0' in body

    def test_failed_in_process_maps_to_bounded_error_code(
        self, monkeypatch, gate_store, fresh_gate_metrics
    ):
        def boom(**k):
            raise RuntimeError("provider exploded")

        monkeypatch.setattr("app.agent.tool_impls.web_search_impl", boom)
        from app.agent.tool_gate import request_tool_execution

        execution = request_tool_execution("web_search", {"query": "q"})
        assert execution.status == "failed"

        body = _body(fresh_gate_metrics)
        assert 'owngpt_agent_tool_calls_total{status="failed",tool="web_search"} 1.0' in body
        assert (
            'owngpt_agent_tool_failures_total{error_code="execution_failed",tool="web_search"} 1.0'
            in body
        )
        # Raw exception text must never become a label value.
        assert "provider exploded" not in body

    def test_guardrail_denial_records_blocked_with_bounded_reason(
        self, gate_store, fresh_gate_metrics
    ):
        from app.agent.tool_gate import request_tool_execution

        execution = request_tool_execution(
            "remember_user_fact", {"fact": "my key is sk-abcdefghijklmnopqrstuvwx"}
        )
        assert execution.status == "denied"

        body = _body(fresh_gate_metrics)
        assert 'owngpt_agent_tool_calls_total{status="blocked",tool="remember_user_fact"} 1.0' in body
        assert (
            'owngpt_agent_tool_blocked_total{reason="secret_content",tool="remember_user_fact"} 1.0'
            in body
        )

    def test_unregistered_tool_collapses_tool_label(self, gate_store, fresh_gate_metrics):
        from app.agent.tool_gate import request_tool_execution

        execution = request_tool_execution("mystery_tool", {})
        assert execution.status == "denied"

        body = _body(fresh_gate_metrics)
        assert 'owngpt_agent_tool_calls_total{status="blocked",tool="other"} 1.0' in body
        assert 'owngpt_agent_tool_blocked_total{reason="unregistered_tool",tool="other"} 1.0' in body
        assert "mystery_tool" not in body

    def test_approval_pending_is_not_counted_until_termination(
        self, gate_store, fresh_gate_metrics
    ):
        from app.agent.tool_gate import request_tool_execution

        execution = request_tool_execution(
            "sm_integration", {"target": "twitter", "action": "post", "content": "hi"}
        )
        assert execution.status == "pending"

        body = _body(fresh_gate_metrics)
        assert "owngpt_agent_tool_calls_total{" not in body
        assert "owngpt_agent_tool_blocked_total{" not in body
        assert "owngpt_agent_tool_failures_total{" not in body

    def test_approved_sandbox_run_records_completed(
        self, monkeypatch, fresh_gate_metrics, gate_store
    ):
        monkeypatch.setattr(
            "app.agent.sandbox.run_sandboxed",
            lambda *a, **k: SimpleNamespace(
                ok=True, timed_out=False, output="posted", error=None, duration_ms=120.0
            ),
        )
        from app.agent.tool_gate import execute_approved

        execution = ToolExecution(tool_name="sm_integration", args={})
        result = execute_approved(execution)
        assert result["ok"] is True

        body = _body(fresh_gate_metrics)
        assert 'owngpt_agent_tool_calls_total{status="completed",tool="sm_integration"} 1.0' in body
        assert 'owngpt_agent_tool_duration_seconds_count{tool="sm_integration"} 1.0' in body

    def test_approved_sandbox_failure_maps_to_sandbox_failed(
        self, monkeypatch, fresh_gate_metrics, gate_store
    ):
        monkeypatch.setattr(
            "app.agent.sandbox.run_sandboxed",
            lambda *a, **k: SimpleNamespace(
                ok=False, timed_out=False, output=None, error="sandbox died", duration_ms=10.0
            ),
        )
        from app.agent.tool_gate import execute_approved

        execute_approved(ToolExecution(tool_name="sm_integration", args={}))
        body = _body(fresh_gate_metrics)
        assert (
            'owngpt_agent_tool_failures_total{error_code="sandbox_failed",tool="sm_integration"} 1.0'
            in body
        )
        assert "sandbox died" not in body

    def test_approved_sandbox_timeout_maps_to_sandbox_timed_out(
        self, monkeypatch, fresh_gate_metrics, gate_store
    ):
        monkeypatch.setattr(
            "app.agent.sandbox.run_sandboxed",
            lambda *a, **k: SimpleNamespace(
                ok=False, timed_out=True, output=None, error="timed out", duration_ms=30_000.0
            ),
        )
        from app.agent.tool_gate import execute_approved

        execute_approved(ToolExecution(tool_name="sm_integration", args={}))
        body = _body(fresh_gate_metrics)
        assert (
            'owngpt_agent_tool_failures_total{error_code="sandbox_timed_out",tool="sm_integration"} 1.0'
            in body
        )

    def test_unregistered_impl_maps_to_unregistered_impl(
        self, fresh_gate_metrics, gate_store
    ):
        from app.agent.tool_gate import execute_approved

        result = execute_approved(ToolExecution(tool_name="nonsense_tool", args={}))
        assert result["ok"] is False
        body = _body(fresh_gate_metrics)
        assert (
            'owngpt_agent_tool_failures_total{error_code="unregistered_impl",tool="other"} 1.0'
            in body
        )

    def test_fail_open_broken_registry_never_breaks_gate(
        self, monkeypatch, gate_store
    ):
        class BrokenMetrics:
            def count(self, *a, **k):
                raise RuntimeError("registry broken")

            def observe(self, *a, **k):
                raise RuntimeError("registry broken")

        monkeypatch.setattr(core_metrics, "agent_metrics", BrokenMetrics())
        monkeypatch.setattr("app.agent.tool_impls.web_search_impl", lambda **k: "ok")
        from app.agent.tool_gate import request_tool_execution

        execution = request_tool_execution("web_search", {"query": "q"})
        assert execution.status == "executed"  # instrumentation never breaks the gate


class TestBlockReasonCodes:
    @pytest.mark.parametrize(
        "reason,expected",
        [
            ("tool is not registered in the guardrail policy", "unregistered_tool"),
            ("tool is deny-listed", "deny_listed"),
            ("fact exceeds 500 chars", "fact_too_long"),
            ("fact must not be empty", "empty_fact"),
            ("memory must not contain credentials or secrets", "secret_content"),
            ("session_id exceeds 128 chars", "session_too_long"),
            ("target 'evil-site' not in allowlist", "invalid_target"),
            ("action 'delete' not in allowlist", "invalid_action"),
            ("mutating tool requires operator approval", "approval_required"),
            ("something completely unexpected", "unknown"),
        ],
    )
    def test_classification_is_bounded_and_deterministic(self, reason, expected):
        from app.agent.tool_gate import _block_reason_code

        assert _block_reason_code(reason) == expected