"""
Phase 3.1 - Production LangGraph agent LLM cost wiring (hermetic tests)

The agent LLM (graph.py call_model) runs AFTER RAGPipeline.process returns,
so its usage_metadata was invisible to the V4.9 TokenBudget and the V4.8
request_completed event. This phase records agent usage back into the SAME
shared budget and closes the trace with ONE complete request_completed.

Covers:
  - capture agent usage (input/output tokens + model) into the budget
  - agent usage added to the request total estimated cost
  - missing / malformed usage is a safe no-op (failure-safe accounting)
  - fallback model when usage_metadata lacks a model
  - combined executor + agent accounting on a single completion event
  - publication through the logging sink with all four correlation IDs
  - completion metadata never contains prompts, content, or secrets
  - shared TokenBudget aggregation (no new tracking mechanism)
  - process(defer_request_completed=True) skips completion; finalize_trace
    then emits exactly one request_completed with the full cost
  - finalize_trace idempotency (no duplicate completion events)
"""

from __future__ import annotations

import logging

import pytest

from app.agent.pipeline.cost import TokenBudget
from app.agent.pipeline.trace import AgentTrace


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
        request_id="req-1",
        execution_id="exe-1",
        session_id="session-1",
        project_id="p-1",
    )
    ctx.token_budget = TokenBudget()
    return ctx


def _completed(ctx):
    return [e for e in ctx.agent_trace.events() if e.event == "request_completed"]


class TestRecordAgentUsage:
    def test_captures_tokens_and_model(self, pipeline, ctx):
        pipeline.record_agent_usage(
            ctx, {"input_tokens": 1200, "completion_tokens": 300, "model": "gpt-4o-mini"}
        )
        by_model = ctx.token_budget.usage_by_model()["gpt-4o-mini"]
        assert by_model["input_tokens"] == 1200
        assert by_model["output_tokens"] == 300
        assert ctx.token_budget.spent_tokens() == 1500

    def test_cost_added_to_request_total(self, pipeline, ctx):
        pipeline.record_agent_usage(
            ctx,
            {"input_tokens": 1_000_000, "completion_tokens": 1_000_000, "model": "gpt-4o-mini"},
        )
        assert ctx.token_budget.total_cost_usd() == 0.75

    def test_accepts_prompt_completion_token_keys(self, pipeline, ctx):
        pipeline.record_agent_usage(
            ctx, {"prompt_tokens": 700, "completion_tokens": 300, "model": "gpt-4o-mini"}
        )
        assert ctx.token_budget.spent_tokens() == 1000

    def test_missing_usage_is_noop(self, pipeline, ctx):
        pipeline.record_agent_usage(ctx, None)
        pipeline.record_agent_usage(ctx, {})
        assert ctx.token_budget.spent_tokens() == 0
        assert ctx.agent_trace.events() == []

    def test_malformed_usage_is_noop(self, pipeline, ctx):
        pipeline.record_agent_usage(ctx, "not-a-dict")
        pipeline.record_agent_usage(ctx, [1, 2, 3])
        pipeline.record_agent_usage(ctx, {"input_tokens": "garbage", "completion_tokens": -5})
        assert ctx.token_budget.spent_tokens() == 0

    def test_fallback_model_used_when_metadata_lacks_model(self, pipeline, ctx):
        pipeline.record_agent_usage(
            ctx, {"input_tokens": 100, "completion_tokens": 50}, fallback_model="gpt-4o"
        )
        assert ctx.token_budget.models_used() == ["gpt-4o"]


class TestFinalizeTrace:
    def test_completion_carries_combined_executor_and_agent_cost(self, pipeline, ctx):
        # Existing V4.9 accounting (executor/synthesis/validation path).
        ctx.token_budget.record("gpt-4o-mini", 1000, 500)
        # The graph agent LLM usage, recorded post-process.
        pipeline.record_agent_usage(
            ctx, {"input_tokens": 2000, "completion_tokens": 1000, "model": "gpt-4o"}
        )
        pipeline.finalize_trace(ctx)

        done = _completed(ctx)
        assert len(done) == 1
        event = done[0]
        assert event.status == "completed"
        assert event.metadata["estimated_cost_usd"] == round(
            ctx.token_budget.total_cost_usd(), 6
        )
        assert event.metadata["models"] == "gpt-4o,gpt-4o-mini"
        assert ctx.agent_trace.events()[-1].event == "request_completed"

    def test_publishes_to_logging_sink_with_all_ids(self, pipeline, ctx, caplog):
        pipeline.record_agent_usage(
            ctx, {"input_tokens": 10, "completion_tokens": 5, "model": "gpt-4o-mini"}
        )
        with caplog.at_level(logging.INFO, logger="app.agent.pipeline.trace"):
            pipeline.finalize_trace(ctx)
        lines = [
            r.getMessage()
            for r in caplog.records
            if r.getMessage().startswith("agent_trace")
        ]
        assert lines, "finalized trace never reached the logging sink"
        last = lines[-1]
        assert "event=request_completed" in last
        for needle in ("request_id=req-1", "execution_id=exe-1",
                       "session_id=session-1", "project_id=p-1"):
            assert needle in last, f"{needle} missing from published trace"
        assert "estimated_cost_usd" in last

    def test_completion_metadata_has_no_prompts_content_or_secrets(self, pipeline, ctx):
        ctx.token_budget.record("gpt-4o-mini", 100, 50)
        pipeline.record_agent_usage(
            ctx, {"input_tokens": 50, "completion_tokens": 25, "model": "gpt-4o-mini"}
        )
        pipeline.finalize_trace(ctx)
        event = _completed(ctx)[0]
        assert set(event.metadata) == {"estimated_cost_usd", "models"}
        payload = " ".join(f"{k}={v}" for k, v in event.metadata.items())
        assert "prompt" not in payload
        assert "content" not in payload
        assert "sk-" not in payload
        assert "hunter2" not in payload

    def test_shared_budget_aggregates_identical_model(self, pipeline, ctx):
        # Executor records twice, agent once — same model → ONE aggregated
        # record (proves agent usage flows through the EXISTING accounting,
        # no second tracker was introduced).
        ctx.token_budget.record("gpt-4o-mini", 100, 50)
        ctx.token_budget.record("gpt-4o-mini", 200, 100)
        pipeline.record_agent_usage(
            ctx, {"input_tokens": 300, "completion_tokens": 150, "model": "gpt-4o-mini"}
        )
        assert len(ctx.token_budget.usage_by_model()) == 1
        usage = ctx.token_budget.usage_by_model()["gpt-4o-mini"]
        assert usage["input_tokens"] == 600
        assert usage["output_tokens"] == 300
        assert usage["total_tokens"] == 900

    def test_no_duplicate_completion(self, pipeline, ctx):
        pipeline.finalize_trace(ctx)
        pipeline.finalize_trace(ctx)
        pipeline.finalize_trace(ctx, status="failed")  # late error path retry
        done = _completed(ctx)
        assert len(done) == 1
        assert done[0].status == "completed"  # first (successful) finalize wins

    def test_status_override_for_failed_flows(self, pipeline, ctx):
        pipeline.finalize_trace(ctx, status="failed")
        assert _completed(ctx)[0].status == "failed"

    def test_validation_failure_marks_completion_failed(self, pipeline, ctx):
        class InvalidValidation:
            valid = False

        ctx.validation = InvalidValidation()
        pipeline.finalize_trace(ctx)
        assert _completed(ctx)[0].status == "failed"

    def test_missing_budget_or_trace_is_noop(self, pipeline):
        from app.agent.pipeline.pipeline import PipelineContext

        bare = PipelineContext(question="q", session_id="s", project_id="p")
        pipeline.finalize_trace(bare)  # no agent_trace
        pipeline.record_agent_usage(bare, {"input_tokens": 1, "completion_tokens": 1})
        bare.agent_trace = AgentTrace(request_id="r", execution_id="e",
                                      session_id="s", project_id="p")
        pipeline.finalize_trace(bare)  # no token_budget → no cost metadata


class TestDeferredCompletion:
    def _build_stubbed_pipeline(self):
        from app.agent.pipeline.pipeline import RAGPipeline
        from app.agent.pipeline.loop import LoopResult
        from app.agent.pipeline.executor import ExecutionResult
        from app.agent.pipeline.synthesizer import SynthesisResult
        from app.agent.pipeline.validator import ValidationResult
        from app.agent.pipeline.planner import Plan, Planner

        plan = Plan(goal="ok", steps=[], requires_tools=False)

        class StubPlanner(Planner):
            def create_plan(self, question, intent, route):
                return plan

        class NoOpSelector:
            def select(self, *a, **k):
                return []

        class StubLoop:
            def run(self, *a, **k):
                return LoopResult(
                    completed=True, iterations=0,
                    stopped_reason="stub",
                    execution=ExecutionResult(
                        status="completed", step_results=[], outputs={},
                        final_output=None,
                    ),
                )

        class StubSynthesizer:
            def synthesize(self, question, plan, execution, context=None):
                return SynthesisResult(answer="ok", success=True)

        class StubValidator:
            def validate(self, question, answer, context=None, execution=None):
                return ValidationResult(
                    valid=True, grounded=True, confidence=1.0, issues=[],
                )

        pl = RAGPipeline(
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
        pl._planner = StubPlanner()
        pl._selector = NoOpSelector()
        pl._tool_selector = NoOpSelector()
        pl._execution_loop = StubLoop()
        pl._synthesizer = StubSynthesizer()
        pl._answer_validator = StubValidator()
        return pl

    def test_deferred_process_skips_completion_until_finalize(self, caplog):
        pl = self._build_stubbed_pipeline()
        with caplog.at_level(logging.INFO, logger="app.agent.pipeline.trace"):
            ctx = pl.process(
                question="hello", session_id="sess-d", project_id="proj-d",
                defer_request_completed=True,
            )
            before = [
                r.getMessage()
                for r in caplog.records
                if r.getMessage().startswith("agent_trace")
            ]
        assert ctx.agent_trace is not None
        assert ctx.token_budget is not None
        # No completion emitted AND nothing published yet.
        assert not _completed(ctx)
        assert not any("request_completed" in line for line in before)

        # The graph agent runs here in production; its usage comes back in.
        pl.record_agent_usage(
            ctx, {"input_tokens": 100, "completion_tokens": 50, "model": "gpt-4o-mini"}
        )
        expected_cost = round(ctx.token_budget.total_cost_usd(), 6)
        pl.finalize_trace(ctx)

        done = _completed(ctx)
        assert len(done) == 1
        assert done[0].metadata["estimated_cost_usd"] == expected_cost

    def test_non_deferred_process_still_emits_completion(self, caplog):
        # Default behavior unchanged: standalone process() callers
        # (contract facade, replay, tooling) keep their completion event.
        pl = self._build_stubbed_pipeline()
        with caplog.at_level(logging.INFO, logger="app.agent.pipeline.trace"):
            ctx = pl.process(question="hello", session_id="sess-nd", project_id="proj-nd")
        done = _completed(ctx)
        assert len(done) == 1