"""
V4.9 - Cost & Token Governance (hermetic tests)

Covers:
  - per-request and per-step token accounting
  - provider/model-aware estimated cost (price table, unknown-model fallback)
  - request/step budget caps and enforcement reasons
  - enforcement BEFORE LLM calls (executor step gate, handler never runs)
  - usage capture from handler metadata into the budget
  - cost metadata on the existing AgentTrace tool/step events
  - synthesis + validation LLM escalation gated by exhausted budgets
  - passive degradation: contexts without a budget behave as before
  - defensive accounting (record() never raises)
  - no new telemetry / no memory access (pure accounting module)
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import app.agent.pipeline.cost as cost_mod
from app.agent.pipeline.cost import (
    DEFAULT_RATE,
    DEFAULT_REQUEST_BUDGET_TOKENS,
    DEFAULT_STEP_BUDGET_TOKENS,
    REASON_REQUEST_EXHAUSTED,
    REASON_STEP_EXHAUSTED,
    TokenBudget,
    TokenUsage,
)
from app.agent.pipeline.executor import Executor, StepResult
from app.agent.pipeline.planner import Plan, PlanStep
from app.agent.pipeline.synthesizer import Synthesizer
from app.agent.pipeline.tool_result import ToolResult
from app.agent.pipeline.trace import AgentTrace
from app.agent.pipeline.validator import AnswerValidator


@pytest.fixture
def executor():
    return Executor()


def make_step(step_id=1, deps=(), action="direct_answer", tool=None):
    return PlanStep(
        step_id=step_id,
        description=f"Step {step_id}",
        action=action,
        tool=tool,
        dependencies=list(deps),
        expected_output="output",
    )


def make_ctx(execution_id="exe-1", request_id="req-1", budget=None):
    from app.agent.pipeline.pipeline import PipelineContext
    from app.agent.pipeline.state import AgentState

    ctx = PipelineContext(question="q", session_id="session-1", project_id="p-1")
    ctx.execution_id = execution_id
    ctx.agent_state = AgentState(request_id=request_id, question="q")
    ctx.agent_trace = AgentTrace(
        request_id=request_id,
        execution_id=execution_id,
        session_id="session-1",
        project_id="p-1",
    )
    ctx.token_budget = budget
    return ctx


def make_plan(*steps):
    return Plan(goal="goal", steps=list(steps), requires_tools=bool(steps))


def make_execution(*step_results):
    from app.agent.pipeline.executor import ExecutionResult

    outputs = {r.step_id: r.output for r in step_results if r.status == "completed"}
    return ExecutionResult(
        status="completed",
        step_results=list(step_results),
        outputs=outputs,
        final_output=outputs[max(outputs)] if outputs else None,
    )


class TestTokenUsage:
    def test_totals(self):
        u = TokenUsage(model="gpt-4o-mini", input_tokens=100, output_tokens=50)
        assert u.total_tokens == 150

    def test_known_model_cost(self):
        u = TokenUsage(model="gpt-4o-mini", input_tokens=1_000_000, output_tokens=1_000_000)
        assert u.cost_usd == 0.0  # cost is computed by the budget, not the record
        b = TokenBudget()
        assert b.estimate_cost("gpt-4o-mini", 1_000_000, 1_000_000) == 0.75

    def test_unknown_model_uses_default_rate(self):
        b = TokenBudget()
        cost = b.estimate_cost("hypothetical-model-x", 1_000_000, 1_000_000)
        assert cost == DEFAULT_RATE[0] + DEFAULT_RATE[1]

    def test_provider_prefixed_model_resolves(self):
        b = TokenBudget()
        assert b.estimate_cost(
            "openai/gpt-4o-mini", 1_000_000, 1_000_000
        ) == b.estimate_cost("gpt-4o-mini", 1_000_000, 1_000_000)

    def test_blank_model_uses_default_rate(self):
        b = TokenBudget()
        assert b.estimate_cost("", 1_000_000, 0) == DEFAULT_RATE[0]


class TestTokenBudgetConstruction:
    def test_default_caps_positive(self):
        b = TokenBudget()
        assert b.request_budget_tokens == DEFAULT_REQUEST_BUDGET_TOKENS
        assert b.per_step_budget_tokens == DEFAULT_STEP_BUDGET_TOKENS

    def test_invalid_caps_rejected(self):
        with pytest.raises(ValueError):
            TokenBudget(request_budget_tokens=0)
        with pytest.raises(ValueError):
            TokenBudget(per_step_budget_tokens=-1)

    def test_custom_rates_override(self):
        b = TokenBudget(rates={"m": (10.0, 20.0)})
        assert b.estimate_cost("m", 1_000_000, 1_000_000) == 30.0
        assert b.estimate_cost("other", 1_000_000, 1_000_000) == DEFAULT_RATE[0] + DEFAULT_RATE[1]


class TestTokenBudgetAccounting:
    def test_accumulates_per_request(self):
        b = TokenBudget()
        b.record("gpt-4o-mini", input_tokens=100, output_tokens=50)
        b.record("gpt-4o-mini", input_tokens=10, output_tokens=10)
        assert b.spent_tokens() == 170
        u = b.usage_by_model()["gpt-4o-mini"]
        assert u["input_tokens"] == 110
        assert u["output_tokens"] == 60

    def test_per_step_accounting(self):
        b = TokenBudget()
        b.record("gpt-4o-mini", input_tokens=100, output_tokens=50, step_id=1)
        b.record("gpt-4o-mini", input_tokens=10, output_tokens=10, step_id=2)
        b.record("gpt-4o-mini", input_tokens=5, output_tokens=5, step_id=1)
        assert b.step_spent(1) == 160
        assert b.step_spent(2) == 20
        assert b.step_spent(99) == 0
        assert b.spent_tokens() == 180

    def test_multi_model_costs(self):
        b = TokenBudget()
        b.record("gpt-4o-mini", input_tokens=1_000_000, output_tokens=1_000_000)
        b.record("deepseek-chat", input_tokens=1_000_000, output_tokens=1_000_000)
        assert b.total_cost_usd() == pytest.approx(0.75 + 1.37)
        assert b.models_used() == ["deepseek-chat", "gpt-4o-mini"]

    def test_models_used_sorted_and_deduplicated(self):
        b = TokenBudget()
        b.record("b-model", input_tokens=1)
        b.record("a-model", input_tokens=1)
        b.record("b-model", input_tokens=1)
        assert b.models_used() == ["a-model", "b-model"]

    def test_usage_snapshot(self):
        b = TokenBudget()
        b.record("m", input_tokens=10, output_tokens=5, step_id=3)
        snap = b.snapshot()
        assert snap["spent_tokens"] == 15
        assert snap["step_tokens"] == {3: 15}
        assert snap["models_used"] == ["m"]
        assert snap["request_budget_tokens"] == DEFAULT_REQUEST_BUDGET_TOKENS

    def test_record_defensive_never_raises(self):
        b = TokenBudget()
        b.record(None, input_tokens=-100, output_tokens="junk", step_id="x")
        b.record("m", input_tokens=None, output_tokens=None)
        b.record("m", input_tokens="10", output_tokens=2.9)
        assert b.spent_tokens() == 12
        assert b.step_spent("x") == 0  # non-int step keys ignored harmlessly


class TestTokenBudgetEnforcement:
    def test_within_budget_allows(self):
        b = TokenBudget(request_budget_tokens=100, per_step_budget_tokens=50)
        assert b.check() is None
        assert b.check(step_id=1) is None

    def test_request_exhausted_reason(self):
        b = TokenBudget(request_budget_tokens=100, per_step_budget_tokens=50)
        b.record("m", input_tokens=100, step_id=1)
        assert b.check(step_id=1) == REASON_REQUEST_EXHAUSTED

    def test_step_exhausted_reason(self):
        b = TokenBudget(request_budget_tokens=10_000, per_step_budget_tokens=50)
        b.record("m", input_tokens=50, output_tokens=1, step_id=1)
        assert b.check(step_id=1) == REASON_STEP_EXHAUSTED
        assert b.check(step_id=2) is None

    def test_request_cap_takes_precedence(self):
        b = TokenBudget(request_budget_tokens=10, per_step_budget_tokens=100)
        b.record("m", input_tokens=10, step_id=1)
        assert b.check(step_id=1) == REASON_REQUEST_EXHAUSTED

    def test_accounting_beyond_cap_stays_accurate(self):
        b = TokenBudget(request_budget_tokens=10, per_step_budget_tokens=10)
        b.record("m", input_tokens=500, step_id=1)
        assert b.spent_tokens() == 500
        assert b.check(step_id=1) == REASON_REQUEST_EXHAUSTED


def _tracking_handler(calls):
    def handler(step, context_str, pipeline_ctx, tool_selection=None):
        calls.append(step.step_id)
        return ToolResult(status="completed", tool="direct_answer", output="ok")
    return handler


def _usage_handler(usage):
    def handler(step, context_str, pipeline_ctx, tool_selection=None):
        return ToolResult(
            status="completed",
            tool="direct_answer",
            output="answer text",
            metadata={"token_usage": usage},
        )
    return handler


class TestExecutorBudgetGate:
    def test_request_exhausted_blocks_before_handler(self, executor, monkeypatch):
        import app.agent.pipeline.executor as executor_mod

        budget = TokenBudget(request_budget_tokens=100, per_step_budget_tokens=100)
        budget.record("gpt-4o-mini", input_tokens=100)  # request exhausted
        ctx = make_ctx(budget=budget)
        calls = []
        monkeypatch.setitem(
            executor_mod._ACTION_HANDLERS, "direct_answer", _tracking_handler(calls)
        )

        result = executor.execute_one(make_step(1), context=ctx)

        assert result.status == "blocked"
        assert result.error == REASON_REQUEST_EXHAUSTED
        assert calls == []  # the LLM call never happened
        events = [e for e in ctx.agent_trace.events() if e.event == "step_blocked"]
        assert len(events) == 1
        assert events[0].metadata["reason"] == REASON_REQUEST_EXHAUSTED
        assert events[0].step_id == 1

    def test_step_budget_exhausted_blocks_same_step(self, executor, monkeypatch):
        import app.agent.pipeline.executor as executor_mod

        budget = TokenBudget(request_budget_tokens=10_000, per_step_budget_tokens=50)
        budget.record("gpt-4o-mini", input_tokens=50, output_tokens=1, step_id=1)
        ctx = make_ctx(budget=budget)
        calls = []
        monkeypatch.setitem(
            executor_mod._ACTION_HANDLERS, "direct_answer", _tracking_handler(calls)
        )

        result = executor.execute_one(make_step(1), context=ctx)

        assert result.status == "blocked"
        assert result.error == REASON_STEP_EXHAUSTED
        assert calls == []

    def test_step_budget_exhausted_does_not_block_other_step(self, executor, monkeypatch):
        import app.agent.pipeline.executor as executor_mod

        budget = TokenBudget(request_budget_tokens=10_000, per_step_budget_tokens=50)
        budget.record("gpt-4o-mini", input_tokens=50, output_tokens=1, step_id=1)
        ctx = make_ctx(budget=budget)
        calls = []
        monkeypatch.setitem(
            executor_mod._ACTION_HANDLERS, "direct_answer", _tracking_handler(calls)
        )

        result = executor.execute_one(make_step(1), context=ctx)
        result2 = executor.execute_one(make_step(2), context=ctx,
                                       step_status={1: "blocked"})

        assert result.status == "blocked"

    def test_no_budget_runs_unrestricted(self, executor, monkeypatch):
        import app.agent.pipeline.executor as executor_mod

        ctx = make_ctx(budget=None)  # pre-V4.9 behavior
        calls = []
        monkeypatch.setitem(
            executor_mod._ACTION_HANDLERS, "direct_answer", _tracking_handler(calls)
        )

        result = executor.execute_one(make_step(1), context=ctx)

        assert result.status == "completed"
        assert calls == [1]

    def test_usage_recorded_into_budget_and_trace(self, executor, monkeypatch):
        import app.agent.pipeline.executor as executor_mod

        budget = TokenBudget()
        ctx = make_ctx(budget=budget)
        usage = {"model": "gpt-4o-mini", "input_tokens": 100, "output_tokens": 50}
        monkeypatch.setitem(
            executor_mod._ACTION_HANDLERS, "direct_answer", _usage_handler(usage)
        )

        result = executor.execute_one(make_step(1), context=ctx)

        assert result.status == "completed"
        assert budget.spent_tokens() == 150
        assert budget.step_spent(1) == 150
        assert budget.models_used() == ["gpt-4o-mini"]

        # ToolResult boundary stays clean: token_usage was popped.
        assert "token_usage" not in (result.tool_result.metadata or {})

        # Cost data attaches to the EXISTING AgentTrace tool event.
        events = [e for e in ctx.agent_trace.events() if e.event == "tool_completed"]
        assert len(events) == 1
        meta = events[0].metadata
        assert meta["model"] == "gpt-4o-mini"
        assert meta["usage_in"] == 100
        assert meta["usage_out"] == 50
        assert meta["cost_usd"] == pytest.approx(0.000045)
        assert meta["error_code"] is None

    def test_usage_without_budget_is_ignored(self, executor, monkeypatch):
        import app.agent.pipeline.executor as executor_mod

        ctx = make_ctx(budget=None)
        usage = {"model": "gpt-4o-mini", "input_tokens": 7, "output_tokens": 3}
        monkeypatch.setitem(
            executor_mod._ACTION_HANDLERS, "direct_answer", _usage_handler(usage)
        )

        result = executor.execute_one(make_step(1), context=ctx)

        assert result.status == "completed"
        assert "token_usage" not in (result.tool_result.metadata or {})
        events = [e for e in ctx.agent_trace.events() if e.event == "tool_completed"]
        assert "usage_in" not in events[0].metadata

    def test_two_steps_account_separately(self, executor, monkeypatch):
        import app.agent.pipeline.executor as executor_mod

        budget = TokenBudget()
        ctx = make_ctx(budget=budget)
        monkeypatch.setitem(
            executor_mod._ACTION_HANDLERS, "direct_answer",
            _usage_handler({"model": "deepseek-chat", "input_tokens": 10, "output_tokens": 5}),
        )

        executor.execute_one(make_step(1), context=ctx)
        executor.execute_one(make_step(2), context=ctx, step_status={1: "completed"})

        assert budget.step_spent(1) == 15
        assert budget.step_spent(2) == 15
        assert budget.spent_tokens() == 30


class TestSynthesizerBudgetGate:
    def _completed_results(self):
        return [
            StepResult(step_id=1, status="completed", output="First output"),
            StepResult(step_id=2, status="completed", output="Second output"),
        ]

    def test_llm_skipped_when_budget_exhausted(self):
        step1, step2 = make_step(1), make_step(2)
        plan = make_plan(step1, step2)
        budget = TokenBudget(request_budget_tokens=10, per_step_budget_tokens=10)
        budget.record("m", input_tokens=10)
        ctx = make_ctx(budget=budget)

        called = {"llm": False}
        real_build = Synthesizer._llm_synthesize

        def fake_llm(*a, **kw):
            called["llm"] = True
            raise AssertionError("build_llm must not run past the budget")

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("app.agent.pipeline.synthesizer.build_llm", fake_llm)
            res = Synthesizer().synthesize(
                "q", plan, make_execution(*self._completed_results()), context=ctx
            )

        assert called["llm"] is False
        assert res.success is True
        assert "First output" in res.answer
        assert "Second output" in res.answer

    def test_usage_recorded_when_budget_has_room(self):
        step1, step2 = make_step(1), make_step(2)
        plan = make_plan(step1, step2)
        budget = TokenBudget()
        ctx = make_ctx(budget=budget)

        class FakeLLM:
            model_name = "gpt-4o-mini"

            def invoke(self, messages):
                return _FakeResponse()

        class _FakeResponse:
            content = "Combined answer."
            usage_metadata = {"input_tokens": 30, "output_tokens": 10}

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("app.agent.pipeline.synthesizer.build_llm", lambda **k: FakeLLM())
            res = Synthesizer().synthesize(
                "q", plan, make_execution(*self._completed_results()), context=ctx
            )

        assert res.answer == "Combined answer."
        assert res.success is True
        assert budget.spent_tokens() == 40
        assert budget.models_used() == ["gpt-4o-mini"]

    def test_without_budget_unchanged(self):
        step1, step2 = make_step(1), make_step(2)
        plan = make_plan(step1, step2)
        ctx = make_ctx(budget=None)

        class FakeLLM:
            def invoke(self, messages):
                class Resp:
                    content = "Combined answer."
                    usage_metadata = {"input_tokens": 30, "output_tokens": 10}
                return Resp()

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("app.agent.pipeline.synthesizer.build_llm", lambda **k: FakeLLM())
            res = Synthesizer().synthesize(
                "q", plan, make_execution(*self._completed_results()), context=ctx
            )

        assert res.answer == "Combined answer."
        assert res.success is True


class TestValidatorBudgetGate:
    def test_llm_skipped_when_budget_exhausted(self):
        budget = TokenBudget(request_budget_tokens=10, per_step_budget_tokens=10)
        budget.record("m", input_tokens=10)
        ctx = make_ctx(budget=budget)
        ctx.grounding_required = False

        called = []

        def fake_build_llm(**kw):
            called.append(kw)
            raise AssertionError("build_llm must not run past the budget")

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("app.agent.pipeline.validator.build_llm", fake_build_llm)
            result = AnswerValidator(use_llm=True).validate(
                "q", "An answer.", context=ctx, execution=None
            )

        assert called == []
        assert result.valid is True  # deterministic result, LLM escalation skipped

    def test_usage_recorded_from_llm_check(self):
        budget = TokenBudget()
        ctx = make_ctx(budget=budget)
        ctx.grounding_required = False

        class FakeLLM:
            model_name = "deepseek-chat"

            def invoke(self, messages):
                class Resp:
                    content = '{"grounded": true, "confidence": 0.9, "issues": []}'
                    usage_metadata = {"input_tokens": 20, "output_tokens": 4}
                return Resp()

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("app.agent.pipeline.validator.build_llm", lambda **k: FakeLLM())
            result = AnswerValidator(use_llm=True).validate(
                "q", "An answer.", context=ctx, execution=None
            )

        assert result.valid is True
        assert budget.spent_tokens() == 24
        assert budget.models_used() == ["deepseek-chat"]


class TestTraceSafety:
    def test_token_usage_metadata_never_enters_trace(self):
        tr = AgentTrace(request_id="req-1", execution_id="exe-1")
        tr.record(
            "execution", "tool_completed", status="completed", step_id=1,
            metadata={"token_usage": {"input_tokens": 5}, "error_code": None},
        )
        event = tr.events()[0]
        assert event.metadata == {"error_code": None}
        assert "token_usage" not in event.metadata


class TestArchitectureConstraints:
    def test_cost_module_is_pure(self):
        src = Path(cost_mod.__file__).read_text(encoding="utf-8")
        for forbidden in (
            "sqlite", "redis", "chromadb", "faiss", "psycopg",
            "services.memory", "memory_v2", "prometheus", "requests",
            "httpx", "tracing",
        ):
            assert forbidden not in src, f"cost.py must not touch {forbidden}"

    def test_cost_module_imports_stdlib_only(self):
        src = Path(cost_mod.__file__).read_text(encoding="utf-8")
        imports = set(re.findall(r"^\s*import (\w+)", src, re.M))
        assert imports <= {"dataclasses", "typing"}

    def test_budget_reuses_trace_correlation_ids(self):
        # The budget itself is context-scoped (request_id/execution_id live
        # on the AgentTrace); cost data is attached through those IDs.
        ctx = make_ctx(execution_id="exe-9", request_id="req-9", budget=TokenBudget())
        assert ctx.agent_trace.request_id == "req-9"
        assert ctx.agent_trace.execution_id == "exe-9"
        assert ctx.token_budget.snapshot()["spent_tokens"] == 0