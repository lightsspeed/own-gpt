"""
V4.8 - Agent Execution Observability (hermetic tests)

Covers:
  - trace creation and request/execution correlation
  - stage events (all nine stages) and step lifecycle ordering
  - tool success / failure / blocked events
  - synthesis and validation events
  - duration recording and stage aggregation
  - secret redaction, raw output exclusion, bounded metadata
  - safe snapshots (immutability)
  - existing observability adapter (logging) integration
  - tracing failure cannot break agent execution
  - derived metrics preparation (no backend)
"""

from __future__ import annotations

import logging
import json

import pytest

from app.agent.pipeline.executor import Executor
from app.agent.pipeline.planner import Plan, PlanStep
from app.agent.pipeline.trace import (
    MAX_METADATA_CHARS,
    VALID_EVENTS,
    VALID_STAGES,
    AgentTrace,
    LoggingTraceObserver,
    TraceEvent,
    TraceObserver,
    record_trace,
)
from app.agent.pipeline.tool_result import ToolResult


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


def make_ctx(execution_id="exe-1", request_id="req-1"):
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
    return ctx


def make_trace():
    return AgentTrace(
        request_id="req-1",
        execution_id="exe-1",
        session_id="session-1",
        project_id="p-1",
    )


class TestTraceCreation:
    def test_trace_holds_correlation_ids(self):
        tr = make_trace()
        assert tr.request_id == "req-1"
        assert tr.execution_id == "exe-1"
        assert tr.session_id == "session-1"
        assert tr.project_id == "p-1"
        assert tr.trace_id == "atr-req-1"
        assert tr.created_at > 0
        assert tr.events() == []

    def test_stage_and_event_vocabulary(self):
        assert "execution" in VALID_STAGES
        assert len(VALID_STAGES) == 9
        assert "step_started" in VALID_EVENTS
        assert "request_completed" in VALID_EVENTS

    def test_record_emits_event_with_metadata(self):
        tr = make_trace()
        tr.record("intent", "intent_classified", status="general", duration_ms=1.5)
        events = tr.events()
        assert len(events) == 1
        e = events[0]
        assert e.stage == "intent"
        assert e.event == "intent_classified"
        assert e.status == "general"
        assert e.duration_ms == 1.5
        assert e.request_id == "req-1"
        assert e.execution_id == "exe-1"
        assert e.session_id == "session-1"
        assert e.project_id == "p-1"
        assert e.timestamp > 0

    def test_invalid_stage_and_event_ignored(self):
        tr = make_trace()
        tr.record("bogus_stage", "step_started")
        tr.record("execution", "bogus_event")
        assert tr.events() == []


class TestLifecycle:
    def test_step_lifecycle_order(self):
        tr = make_trace()
        tr.record("execution", "step_started", step_id=1, tool="t")
        tr.record("execution", "tool_completed", step_id=1, tool="t", status="completed")
        tr.record("execution", "step_completed", step_id=1, tool="t")
        names = [e.event for e in tr.events()]
        assert names == ["step_started", "tool_completed", "step_completed"]

    def test_tool_success_failure_blocked_events(self):
        tr = make_trace()
        tr.record("execution", "tool_completed", status="completed", tool="web_search")
        tr.record("execution", "tool_failed", status="failed", tool="tavily_search")
        tr.record("execution", "tool_blocked", status="blocked", tool="memory_write")
        by_event = {e.event: e for e in tr.events()}
        assert by_event["tool_completed"].status == "completed"
        assert by_event["tool_failed"].status == "failed"
        assert by_event["tool_blocked"].status == "blocked"

    def test_tool_event_mapping_from_tool_status(self):
        assert AgentTrace.tool_event_for("completed") == "tool_completed"
        assert AgentTrace.tool_event_for("blocked") == "tool_blocked"
        assert AgentTrace.tool_event_for("failed") == "tool_failed"
        assert AgentTrace.tool_event_for("timeout") == "tool_failed"
        assert AgentTrace.tool_event_for("empty") == "tool_failed"

    def test_synthesis_and_validation_events(self):
        tr = make_trace()
        tr.record("synthesis", "synthesis_completed", status="completed")
        tr.record("validation", "validation_completed", status="valid")
        names = {e.event for e in tr.events()}
        assert "synthesis_completed" in names
        assert "validation_completed" in names

    def test_all_nine_stages_recordable(self):
        tr = make_trace()
        for stage in sorted(VALID_STAGES):
            tr.record(stage, "plan_created" if stage == "planning" else (
                "intent_classified" if stage == "intent" else
                "route_selected" if stage == "routing" else
                "capability_selected" if stage == "capability_selection" else
                "tool_selected" if stage == "tool_selection" else
                "step_started" if stage == "execution" else
                "synthesis_completed" if stage == "synthesis" else
                "validation_completed" if stage == "validation" else
                "request_started"))
        assert len(tr.events()) == 9

    def test_duration_recording_and_stage_aggregation(self):
        tr = make_trace()
        tr.record("execution", "step_completed", duration_ms=10.0, step_id=1)
        tr.record("execution", "step_completed", duration_ms=20.5, step_id=2)
        tr.record("synthesis", "synthesis_completed", duration_ms=5.0)
        m = tr.metrics()
        assert m["agent_step_duration"] == 30.5
        assert m["agent_stage_duration"]["execution"] == 30.5
        assert m["agent_stage_duration"]["synthesis"] == 5.0


class TestTraceSafety:
    def test_authorization_code_redacted(self):
        tr = make_trace()
        tr.record("execution", "step_started", metadata={
            "authorization_code": "axc-1234567890-secret",
        })
        assert tr.events()[0].metadata == {}

    def test_api_key_and_code_value_redacted(self):
        tr = make_trace()
        tr.record("execution", "tool_completed", metadata={
            "note": "used key sk-abcdefghijklmnop123456",
            "label": "code=abcdefghij12345xyz",
        })
        md = tr.events()[0].metadata
        assert "sk-" not in md["note"]
        assert "[REDACTED]" in md["note"]
        assert "[REDACTED]" in md["label"]

    def test_raw_output_and_memory_content_excluded(self):
        tr = make_trace()
        tr.record("execution", "tool_completed", metadata={
            "output": "raw web result with secrets",
            "memory_fact": "user password is hunter2",
            "prompt": "system prompt text",
            "query": "question text",
            "chunk_count": 4,
        })
        md = tr.events()[0].metadata
        assert md == {"chunk_count": 4}

    def test_metadata_size_bounded(self):
        tr = make_trace()
        big = {f"key_{i}": "x" * 200 for i in range(300)}
        tr.record("execution", "tool_completed", metadata=big)
        payload = json.dumps(tr.events()[0].metadata)
        assert len(payload) <= MAX_METADATA_CHARS

    def test_exception_message_sanitized(self):
        tr = make_trace()
        tr.record("execution", "tool_failed", metadata={
            "error": "provider boom with sk-zzzyyyxxx987654321 should vanish",
        })
        md = tr.events()[0].metadata
        assert "sk-" not in md["error"]
        assert "[REDACTED]" in md["error"]


class TestSnapshots:
    def test_events_returns_copies(self):
        tr = make_trace()
        tr.record("intent", "intent_classified")
        first = tr.events()
        first.clear()
        assert len(tr.events()) == 1

    def test_snapshot_is_independent(self):
        tr = make_trace()
        tr.record("intent", "intent_classified")
        snap = tr.snapshot()
        snap.record("routing", "route_selected")
        assert len(tr.events()) == 1
        assert len(snap.events()) == 2

    def test_to_dict_roundtrip_shape(self):
        tr = make_trace()
        tr.record("routing", "route_selected", status="rag")
        d = tr.to_dict()
        assert d["request_id"] == "req-1"
        assert d["events"][0]["stage"] == "routing"
        assert d["events"][0]["event"] == "route_selected"


class TestMetricsPreparation:
    def test_full_metrics_shape(self):
        tr = make_trace()
        tr.record("execution", "step_started", step_id=1, tool="t")
        tr.record("execution", "tool_completed", step_id=1, tool="t", duration_ms=8.0)
        tr.record("execution", "tool_failed", step_id=2, tool="t2", duration_ms=3.0)
        tr.record("execution", "tool_blocked", step_id=3, tool="t3")
        tr.record("execution", "step_completed", step_id=1, duration_ms=8.0)
        tr.record("execution", "request_completed", status="partial", duration_ms=50.0)
        m = tr.metrics()
        assert m["agent_requests_total"] == 1
        assert m["agent_requests_failed"] == 0
        assert m["agent_requests_partial"] == 1
        assert m["agent_step_duration"] == 8.0
        assert m["agent_tool_duration"] == 8.0
        assert m["agent_tool_failures"] == 1
        assert m["agent_tool_blocked"] == 1
        assert m["agent_stage_duration"]["execution"] == 69.0

    def test_failed_request_counter(self):
        tr = make_trace()
        tr.record("execution", "request_completed", status="failed")
        assert tr.metrics()["agent_requests_failed"] == 1
        assert tr.metrics()["agent_requests_partial"] == 0


class TestObservabilityAdapter:
    def test_logging_observer_uses_existing_logger(self, caplog):
        tr = make_trace()
        tr.record("intent", "intent_classified", status="general")
        observer = LoggingTraceObserver()
        with caplog.at_level(logging.INFO, logger="app.agent.pipeline.trace"):
            observer.publish(tr)
        lines = [r for r in caplog.records if r.getMessage().startswith("agent_trace")]
        assert len(lines) == 1
        assert 'event=intent_classified' in lines[0].getMessage()
        assert 'request_id=req-1' in lines[0].getMessage()
        assert 'execution_id=exe-1' in lines[0].getMessage()

    def test_publish_delivers_snapshot_to_custom_observer(self):
        received = []

        class FakeObserver(TraceObserver):
            def publish(self, trace):
                received.append(trace)

        tr = make_trace()
        tr.record("routing", "route_selected")
        tr.publish(FakeObserver())
        assert len(received) == 1
        events = received[0].events()
        assert events[0].event == "route_selected"

    def test_failing_observer_never_raises(self):
        class BrokenObserver(TraceObserver):
            def publish(self, trace):
                raise RuntimeError("backend down")

        tr = make_trace()
        tr.record("routing", "route_selected")
        tr.publish(BrokenObserver())  # must not raise


class TestSinkPublication:
    """The completed AgentTrace must reach a real sink, not just memory.

    AgentTrace events exist only in memory until an observer consumes the
    trace; RAGPipeline.process() publishes via LoggingTraceObserver so the
    existing logger becomes the runtime sink."""
    def _build_stubbed_pipeline(self):
        from unittest import mock
        from app.agent.pipeline.pipeline import RAGPipeline
        from app.agent.pipeline.loop import LoopResult
        from app.agent.pipeline.executor import ExecutionResult
        from app.agent.pipeline.synthesizer import SynthesisResult
        from app.agent.pipeline.validator import ValidationResult
        from app.agent.pipeline.planner import Plan, Planner

        class EmptyStore:
            def similarity_search_with_score(self, *a, **k):
                return []

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
                record_trace(context, "synthesis", "synthesis_completed",
                             status="completed")
                return SynthesisResult(answer="ok", success=True)

        class StubValidator:
            def validate(self, question, answer, context=None, execution=None):
                record_trace(context, "validation", "validation_completed",
                             status="valid")
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

    def test_process_publishes_complete_trace_to_logging_sink(self, caplog):
        pl = self._build_stubbed_pipeline()
        with caplog.at_level(logging.INFO, logger="app.agent.pipeline.trace"):
            ctx = pl.process(
                question="hello", session_id="sess-x", project_id="proj-x",
            )

        lines = [
            r.getMessage()
            for r in caplog.records
            if r.getMessage().startswith("agent_trace")
        ]
        assert lines, "AgentTrace was never published to the logging sink"
        assert lines[0].startswith(
            "agent_trace request_id="
        ) and "event=request_started" in lines[0]
        assert "event=request_completed" in lines[-1]

        # Full correlation propagation on the published lines
        for needle in ("request_id=", "execution_id=", "session_id=sess-x",
                       "project_id=proj-x"):
            assert needle in lines[-1], f"{needle} missing from published trace"
            assert needle in lines[0], f"{needle} missing from published trace"

        # The trace closes only after the final lifecycle event
        assert "estimated_cost_usd" in lines[-1]

    def test_publish_at_process_end_counts_all_lifecycle_events(self, caplog):
        pl = self._build_stubbed_pipeline()
        with caplog.at_level(logging.INFO, logger="app.agent.pipeline.trace"):
            pl.process(question="q", session_id="s1", project_id="p1")
        lines = [
            r.getMessage()
            for r in caplog.records
            if r.getMessage().startswith("agent_trace")
        ]
        events = [l.split("event=")[1].split(" ")[0] for l in lines]
        assert events[0] == "request_started"
        assert events[-1] == "request_completed"
        assert {"intent_classified", "route_selected", "plan_created",
                "capability_selected", "tool_selected",
                "synthesis_completed", "validation_completed"} <= set(events)


class TestPassivity:
    def test_record_trace_helper_never_raises(self):
        class BadCtx:
            agent_trace = object()

        record_trace(BadCtx(), "execution", "step_started")  # no agent_trace.record
        record_trace(None, "execution", "step_started")       # no context at all

    def test_trace_record_with_bad_metadata_never_raises(self):
        tr = make_trace()
        tr.record("execution", "tool_completed", metadata={"weird": object()})
        assert tr.events()[0].metadata == {}
        assert tr.events()[0].stage == "execution"

    def test_broken_agent_trace_cannot_break_executor(self, executor):
        ctx = make_ctx()

        class BrokenTrace:
            def record(self, *a, **k):
                raise RuntimeError("tracing exploded")

        ctx.agent_trace = BrokenTrace()

        def handler(step, context_str, pipeline_ctx, tool_selection=None):
            return ToolResult(status="completed", tool="t", output="still works")

        from unittest import mock
        from app.agent.pipeline import executor as executor_module

        with mock.patch.dict(executor_module._ACTION_HANDLERS, {"direct_answer": handler}):
            result = executor.execute_one(make_step(), context=ctx)
        assert result.status == "completed"
        assert result.output == "still works"


class TestExecutorTraceIntegration:
    @pytest.fixture
    def executor(self):
        return Executor()

    def test_executor_records_step_and_tool_events(self, executor):
        ctx = make_ctx()

        def handler(step, context_str, pipeline_ctx, tool_selection=None):
            return ToolResult(status="completed", tool="web_search", output="data")

        from unittest import mock
        from app.agent.pipeline import executor as executor_module

        with mock.patch.dict(executor_module._ACTION_HANDLERS, {"direct_answer": handler}):
            result = executor.execute_one(make_step(), context=ctx)

        assert result.status == "completed"
        events = ctx.agent_trace.events()
        names = [e.event for e in events]
        assert names == ["step_started", "step_completed", "tool_completed"]
        step_evt = events[0]
        assert step_evt.step_id == 1
        assert step_evt.execution_id == "exe-1"
        assert step_evt.stage == "execution"

    def test_executor_records_blocked_tool_events(self, executor):
        ctx = make_ctx()

        def handler(step, context_str, pipeline_ctx, tool_selection=None):
            return ToolResult(status="blocked", tool="t", error_code="TOOL_BLOCKED")

        from unittest import mock
        from app.agent.pipeline import executor as executor_module

        with mock.patch.dict(executor_module._ACTION_HANDLERS, {"direct_answer": handler}):
            result = executor.execute_one(make_step(), context=ctx)
        assert result.status == "blocked"
        names = [e.event for e in ctx.agent_trace.events()]
        assert names == ["step_started", "step_blocked", "tool_blocked"]
        assert ctx.agent_trace.events()[-1].metadata["error_code"] == "TOOL_BLOCKED"

    def test_executor_records_failed_tool_events(self, executor):
        ctx = make_ctx()

        def handler(step, context_str, pipeline_ctx, tool_selection=None):
            raise TimeoutError("slow")

        from unittest import mock
        from app.agent.pipeline import executor as executor_module

        with mock.patch.dict(executor_module._ACTION_HANDLERS, {"direct_answer": handler}):
            result = executor.execute_one(make_step(), context=ctx)
        assert result.status == "failed"
        names = [e.event for e in ctx.agent_trace.events()]
        assert names == ["step_started", "step_failed", "tool_failed"]
        assert ctx.agent_trace.events()[-1].metadata["error_code"] == "TOOL_TIMEOUT"

    def test_policy_block_records_step_blocked(self, executor):
        ctx = make_ctx()
        step = make_step(step_id=1, deps=[9])
        result = executor.execute_one(
            step,
            context=ctx,
            step_status={9: "failed"},
        )
        assert result.status == "blocked"
        names = [e.event for e in ctx.agent_trace.events()]
        assert names == ["step_blocked"]