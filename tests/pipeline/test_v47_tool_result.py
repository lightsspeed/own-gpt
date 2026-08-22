"""
V4.7 - Tool Result & Failure Handling (hermetic tests)

Covers:
  - ToolResult model: statuses, stable error taxonomy, sanitized error
  - boundary normalization of tool_gate outcomes
  - exception normalization (provider / timeout / invalid args / generic)
  - malformed tool output handling
  - executor integration: StepResult consumes ToolResult, step semantics kept
  - failed/blocked dependencies still block dependents
  - synthesis of partial failure and single empty step
  - validation flags answers relying on failed/empty tool results
  - lineage preservation (step_id, execution_id, latency)
  - no raw provider/secrets text as primary client error
"""

from __future__ import annotations

import pytest

from app.agent.pipeline.executor import ExecutionResult, Executor, StepResult
from app.agent.pipeline.planner import Plan, PlanStep
from app.agent.pipeline.synthesizer import Synthesizer
from app.agent.pipeline.tool_result import (
    ERROR_CODES,
    MAX_ERROR_CHARS,
    VALID_TOOL_STATUSES,
    ToolResult,
    normalize_exception,
    normalize_execution,
)
from app.agent.pipeline.validator import AnswerValidator


@pytest.fixture
def executor():
    return Executor()


@pytest.fixture
def synth():
    return Synthesizer()


def make_step(step_id=1, deps=(), action="direct_answer", tool=None):
    return PlanStep(
        step_id=step_id,
        description=f"Step {step_id}",
        action=action,
        tool=tool,
        dependencies=list(deps),
        expected_output="output",
    )


def make_ctx(execution_id="exe-1", request_id="req-1"):
    from app.agent.pipeline.pipeline import PipelineContext
    from app.agent.pipeline.state import AgentState

    ctx = PipelineContext(question="q", session_id="session-1", project_id="p-1")
    ctx.execution_id = execution_id
    ctx.agent_state = AgentState(request_id=request_id, question="q")
    return ctx


def gate(status, result="", error=None):
    class _G:
        pass

    g = _G()
    g.status = status
    g.result = result or ""
    g.error = error
    return g


class TestToolResultModel:
    def test_valid_statuses_enumerated(self):
        assert VALID_TOOL_STATUSES == {
            "completed", "failed", "blocked", "empty", "timeout"
        }

    def test_error_codes_enumerated(self):
        assert ERROR_CODES == {
            "TOOL_FAILED", "TOOL_BLOCKED", "TOOL_EMPTY", "TOOL_TIMEOUT",
            "PROVIDER_UNAVAILABLE", "INVALID_TOOL_ARGUMENTS",
            "AUTHORIZATION_REQUIRED",
        }

    def test_invalid_status_rejected(self):
        with pytest.raises(ValueError):
            ToolResult(status="bogus", tool="t")

    def test_to_dict_serializes_all_fields(self):
        tr = ToolResult(
            status="completed", tool="web_search", output="results",
            execution_id="exe-1", step_id=2, latency_ms=12.5,
            metadata={"chunks": 3},
        )
        d = tr.to_dict()
        assert d["status"] == "completed"
        assert d["tool"] == "web_search"
        assert d["execution_id"] == "exe-1"
        assert d["step_id"] == 2
        assert d["latency_ms"] == 12.5
        assert d["metadata"] == {"chunks": 3}
        assert d["error_code"] is None

    def test_error_detail_never_primary_and_capped(self):
        tr = ToolResult(
            status="failed", tool="t",
            error_code="PROVIDER_UNAVAILABLE",
            error="openai.api.Error: connection refused with secret token abc123 " * 50,
        )
        assert tr.error_code == "PROVIDER_UNAVAILABLE"
        assert len(tr.error) <= MAX_ERROR_CHARS
        assert tr.to_dict()["error_code"] == "PROVIDER_UNAVAILABLE"


class TestBoundaryNormalization:
    def test_executed_with_output_completed(self):
        tr = normalize_execution(
            gate("executed", "facts saved"), tool="remember_user_fact"
        )
        assert tr.status == "completed"
        assert tr.output == "facts saved"
        assert tr.error_code is None

    def test_allowed_with_output_completed(self):
        tr = normalize_execution(
            gate("allowed", "kb chunk"), tool="search_knowledge_base"
        )
        assert tr.status == "completed"

    def test_executed_empty_becomes_empty(self):
        tr = normalize_execution(gate("executed", "  "), tool="web_search")
        assert tr.status == "empty"
        assert tr.error_code == "TOOL_EMPTY"

    def test_denied_becomes_blocked(self):
        tr = normalize_execution(gate("denied", error="guardrail policy"), tool="t")
        assert tr.status == "blocked"
        assert tr.error_code == "TOOL_BLOCKED"

    def test_pending_becomes_authorization_required(self):
        tr = normalize_execution(gate("pending", error="awaiting operator"), tool="t")
        assert tr.status == "blocked"
        assert tr.error_code == "AUTHORIZATION_REQUIRED"

    def test_timed_out_becomes_timeout(self):
        tr = normalize_execution(gate("timed_out", error="slow"), tool="t")
        assert tr.status == "timeout"
        assert tr.error_code == "TOOL_TIMEOUT"

    def test_failed_becomes_failed(self):
        tr = normalize_execution(gate("failed", error="boom"), tool="t")
        assert tr.status == "failed"
        assert tr.error_code == "TOOL_FAILED"

    def test_unknown_status_fails_closed(self):
        tr = normalize_execution(gate("mystery"), tool="t")
        assert tr.status == "failed"
        assert tr.error_code == "TOOL_FAILED"


class TestExceptionNormalization:
    def test_timeout_error(self):
        tr = normalize_exception(TimeoutError("slow provider"), tool="t")
        assert tr.status == "timeout"
        assert tr.error_code == "TOOL_TIMEOUT"

    def test_value_error_invalid_arguments(self):
        tr = normalize_exception(ValueError("bad query arg"), tool="t")
        assert tr.error_code == "INVALID_TOOL_ARGUMENTS"

    def test_provider_error_class(self):
        class APIConnectionError(Exception):
            pass

        tr = normalize_exception(APIConnectionError("provider down"), tool="t")
        assert tr.error_code == "PROVIDER_UNAVAILABLE"

    def test_generic_exception(self):
        tr = normalize_exception(RuntimeError("whatever"), tool="t")
        assert tr.status == "failed"
        assert tr.error_code == "TOOL_FAILED"

    def test_provider_text_not_primary(self):
        tr = normalize_exception(
            RuntimeError("openai API invalid key sk-abc123xyz"), tool="t"
        )
        assert tr.error_code == "TOOL_FAILED"
        assert "sk-abc123xyz" not in tr.error


class TestExecutorIntegration:
    def _run(self, executor, step, ctx, patch_handler, step_outputs=None,
             step_status=None):
        from unittest import mock

        from app.agent.pipeline import executor as executor_module

        with mock.patch.dict(executor_module._ACTION_HANDLERS,
                             {"direct_answer": patch_handler}):
            return executor.execute_one(
                step=step,
                context=ctx,
                step_outputs=step_outputs or {},
                step_status=step_status or {},
            )

    def test_completed_tool_result_consumed_by_step_result(self, executor):
        def handler(step, context_str, pipeline_ctx, tool_selection=None):
            return ToolResult(status="completed", tool="my_tool", output="good data")

        ctx = make_ctx()
        result = self._run(executor, make_step(), ctx, handler)

        assert result.status == "completed"
        assert result.output == "good data"
        tr = result.tool_result
        assert tr is not None
        assert tr.status == "completed"
        assert tr.step_id == 1
        assert tr.execution_id == "exe-1"
        assert tr.latency_ms >= 0.0

    def test_blocked_tool_result_maps_to_blocked_step(self, executor):
        def handler(step, context_str, pipeline_ctx, tool_selection=None):
            return ToolResult(
                status="blocked", tool="t",
                error_code="TOOL_BLOCKED", error="guardrail denied",
            )

        result = self._run(executor, make_step(), make_ctx(), handler)
        assert result.status == "blocked"
        assert result.output == ""
        assert result.tool_result.error_code == "TOOL_BLOCKED"
        assert "guardrail denied" in result.error

    def test_timeout_tool_result_maps_to_failed_step(self, executor):
        def handler(step, context_str, pipeline_ctx, tool_selection=None):
            return ToolResult(status="timeout", tool="t", error_code="TOOL_TIMEOUT")

        result = self._run(executor, make_step(), make_ctx(), handler)
        assert result.status == "failed"
        assert result.tool_result.error_code == "TOOL_TIMEOUT"

    def test_raised_value_error_normalized_invalid_arguments(self, executor):
        def handler(step, context_str, pipeline_ctx, tool_selection=None):
            raise ValueError("bad arg")

        result = self._run(executor, make_step(), make_ctx(), handler)
        assert result.status == "failed"
        assert result.tool_result.error_code == "INVALID_TOOL_ARGUMENTS"

    def test_raised_timeout_normalized(self, executor):
        def handler(step, context_str, pipeline_ctx, tool_selection=None):
            raise TimeoutError("slow")

        result = self._run(executor, make_step(), make_ctx(), handler)
        assert result.tool_result.status == "timeout"
        assert result.tool_result.error_code == "TOOL_TIMEOUT"

    def test_malformed_non_string_output(self, executor):
        def handler(step, context_str, pipeline_ctx, tool_selection=None):
            return {"not": "a string"}

        result = self._run(executor, make_step(), make_ctx(), handler)
        assert result.status == "failed"
        assert result.tool_result.error_code == "TOOL_FAILED"
        assert "malformed" in result.tool_result.error

    def test_plain_str_handler_still_completes(self, executor):
        def handler(step, context_str, pipeline_ctx, tool_selection=None):
            return "legacy text"

        result = self._run(executor, make_step(), make_ctx(), handler)
        assert result.status == "completed"
        assert result.output == "legacy text"
        assert result.tool_result.status == "completed"

    def test_memory_gate_denial_no_longer_raises(self, executor, monkeypatch):
        plan = Plan(
            goal="mem",
            steps=[make_step(step_id=1, action="memory", tool="remember_user_fact")],
            requires_tools=True,
        )
        monkeypatch.setattr(
            "app.agent.pipeline.executor.request_tool_execution",
            lambda tool, args: gate("denied", error="policy"),
        )
        result = executor.execute_one(plan.steps[0], context=make_ctx())
        assert result.status == "blocked"
        assert result.tool_result.error_code == "TOOL_BLOCKED"

    def test_failed_dependency_still_blocks_dependent(self, executor):
        def handler(step, context_str, pipeline_ctx, tool_selection=None):
            return ToolResult(
                status="failed", tool="t",
                error_code="TOOL_FAILED", error="upstream broke",
            )

        ctx = make_ctx()
        dep = self._run(executor, make_step(step_id=1), ctx, handler)
        assert dep.status == "failed"
        depends_on_failed = executor.execute_one(
            step=make_step(step_id=2, deps=[1]),
            context=ctx,
            step_outputs={},
            step_status={1: "failed"},
        )
        assert depends_on_failed.status == "blocked"
        assert depends_on_failed.tool_result is None


class TestSynthesisPartialFailure:
    def test_single_empty_step_returns_no_result(self, synth):
        plan = Plan(
            goal="q", steps=[make_step(step_id=1, action="web_search")],
            requires_tools=True,
        )
        sr = StepResult(
            step_id=1, status="completed", output="",
            tool_result=ToolResult(status="empty", tool="web_search",
                                   error_code="TOOL_EMPTY"),
        )
        execution = ExecutionResult(status="completed", step_results=[sr],
                                    outputs={1: ""})
        res = synth.synthesize("q", plan, execution)
        assert res.success is False
        assert "no usable result" in res.answer
        assert res.step_summaries[0].tool_status == "empty"
        assert res.step_summaries[0].error_code == "TOOL_EMPTY"

    def test_single_timeout_step_returns_timed_out(self, synth):
        plan = Plan(
            goal="q", steps=[make_step(step_id=1, action="web_search")],
            requires_tools=True,
        )
        sr = StepResult(
            step_id=1, status="failed", output="",
            tool_result=ToolResult(status="timeout", tool="web_search",
                                   error_code="TOOL_TIMEOUT"),
        )
        execution = ExecutionResult(status="failed", step_results=[sr], outputs={})
        res = synth.synthesize("q", plan, execution)
        assert res.success is False
        assert "timed out" in res.answer

    def test_partial_with_completed_and_empty(self, synth):
        plan = Plan(
            goal="q",
            steps=[
                make_step(step_id=1, action="knowledge"),
                make_step(step_id=2, action="web_search", deps=[1]),
            ],
            requires_tools=True,
        )
        good = StepResult(
            step_id=1, status="completed", output="kb answer",
            tool_result=ToolResult(status="completed", tool="search_knowledge_base",
                                   output="kb answer"),
        )
        empty = StepResult(
            step_id=2, status="completed", output="",
            tool_result=ToolResult(status="empty", tool="web_search",
                                   error_code="TOOL_EMPTY"),
        )
        execution = ExecutionResult(
            status="partial", step_results=[good, empty], outputs={1: "kb answer"},
        )
        res = synth.synthesize("q", plan, execution)
        assert res.success is True
        assert "kb answer" in res.answer
        assert "usable results" in res.answer

    def test_all_failed_steps_listed(self, synth):
        plan = Plan(
            goal="q", steps=[make_step(step_id=1, action="web_search")],
            requires_tools=True,
        )
        sr = StepResult(
            step_id=1, status="failed", output="",
            tool_result=ToolResult(status="failed", tool="web_search",
                                   error_code="PROVIDER_UNAVAILABLE"),
        )
        execution = ExecutionResult(status="failed", step_results=[sr], outputs={})
        res = synth.synthesize("q", plan, execution)
        assert res.success is False
        assert "encountered an error" in res.answer
        assert res.step_summaries[0].error_code == "PROVIDER_UNAVAILABLE"


class TestValidationFailedEvidence:
    def _ctx(self, grounding_required=True, has_evidence=True):
        class _C:
            pass

        c = _C()
        c.grounding_required = grounding_required
        c.has_evidence = has_evidence
        c.source_count = 3 if has_evidence else 0
        return c

    def test_completed_tool_result_with_evidence_grounded(self):
        sr = StepResult(
            step_id=1, status="completed", output="kb answer",
            tool_result=ToolResult(status="completed", tool="search_knowledge_base",
                                   output="kb answer"),
        )
        execution = ExecutionResult(status="completed", step_results=[sr],
                                    outputs={1: "kb answer"})
        v = AnswerValidator().validate("q", "kb answer", self._ctx(), execution)
        assert v.valid is True
        assert v.grounded is True

    def test_empty_tool_result_never_grounds(self):
        sr = StepResult(
            step_id=1, status="completed", output="",
            tool_result=ToolResult(status="empty", tool="web_search",
                                   error_code="TOOL_EMPTY"),
        )
        execution = ExecutionResult(status="completed", step_results=[sr], outputs={})
        v = AnswerValidator().validate("q", "guess", self._ctx(), execution)
        assert v.valid is False
        assert v.grounded is False
        assert any("no usable tool result" in i for i in v.issues)
        assert any("failed or empty" in i for i in v.issues)

    def test_failed_tool_result_flagged(self):
        sr = StepResult(
            step_id=1, status="failed", output="",
            tool_result=ToolResult(status="failed", tool="t",
                                   error_code="TOOL_FAILED"),
        )
        execution = ExecutionResult(status="failed", step_results=[sr], outputs={})
        v = AnswerValidator().validate("q", "answer", self._ctx(), execution)
        assert any("failed or empty" in i for i in v.issues)
        assert any("no usable tool result" in i for i in v.issues)

    def test_legacy_step_results_without_tool_result_unchanged(self):
        sr = StepResult(step_id=1, status="completed", output="kb answer")
        execution = ExecutionResult(status="completed", step_results=[sr],
                                    outputs={1: "kb answer"})
        v = AnswerValidator().validate("q", "kb answer", self._ctx(), execution)
        assert v.valid is True
        assert v.grounded is True
        assert v.issues == []

