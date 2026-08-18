"""
V4.6 - Agent Memory & Execution Continuity (hermetic tests)

Covers:
  - structured StepContext carrying request/execution/session/project ids
  - dependency-aware propagation: only declared dependencies, declared order
  - isolation between unrelated steps
  - missing / failed dependency handling
  - bounded propagation with safe truncation (metadata survives)
  - lineage preservation (step_id + execution_id per propagated entry)
  - executor integration: StepResult carries StepContext for synthesis/audit
  - NO second memory system is introduced
"""

from __future__ import annotations

import inspect

import pytest

from app.agent.pipeline.executor import Executor
from app.agent.pipeline.planner import Plan, PlanStep
from app.agent.pipeline.step_context import (
    DEFAULT_MAX_OUTPUT_CHARS,
    StepContextBuilder,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def builder():
    return StepContextBuilder()


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


def make_ctx(
    question="q",
    session_id="session-1",
    project_id="project-1",
    user_id="user-1",
    request_id="req-1",
    execution_id="exe-1",
):
    from app.agent.pipeline.pipeline import PipelineContext
    from app.agent.pipeline.state import AgentState

    ctx = PipelineContext(
        question=question,
        session_id=session_id,
        project_id=project_id,
        user_id=user_id,
    )
    ctx.execution_id = execution_id
    ctx.agent_state = AgentState(request_id=request_id, question=question)
    return ctx


# ── Test 1: StepContext carries execution identity ────────────────────────────

class TestExecutionIdentity:
    def test_step_context_preserves_ids(self, builder):
        step = make_step(step_id=5, deps=[1])
        sc = builder.build(
            step=step,
            step_outputs={1: "out-1"},
            request_id="req-1",
            execution_id="exe-1",
            session_id="session-1",
            project_id="project-1",
        )
        assert sc.step_id == 5
        assert sc.request_id == "req-1"
        assert sc.execution_id == "exe-1"
        assert sc.session_id == "session-1"
        assert sc.project_id == "project-1"
        assert sc.entries[0].execution_id == "exe-1"

    def test_pipeline_context_exposes_execution_id(self):
        ctx = make_ctx()
        assert ctx.execution_id == "exe-1"
        assert ctx.agent_state.request_id == "req-1"

    def test_default_max_output_chars(self):
        assert DEFAULT_MAX_OUTPUT_CHARS == 4000

    def test_builder_rejects_non_positive_bound(self):
        with pytest.raises(ValueError):
            StepContextBuilder(max_output_chars=0)


# ── Test 2: Dependency-aware propagation ──────────────────────────────────────

class TestDependencyPropagation:
    def test_receives_only_declared_dependencies_in_order(self, builder):
        step = make_step(step_id=3, deps=[2, 1])
        sc = builder.build(
            step=step,
            step_outputs={1: "out-1", 2: "out-2", 3: "unrelated"},
        )
        assert [e.step_id for e in sc.entries] == [2, 1]
        assert [e.output for e in sc.entries] == ["out-2", "out-1"]

    def test_no_dependencies_yields_empty_context(self, builder):
        step = make_step(step_id=1, deps=[])
        sc = builder.build(step=step, step_outputs={2: "leak"})
        assert sc.entries == []
        assert sc.to_plain_text() == ""

    def test_unrelated_step_output_does_not_leak(self, builder):
        step = make_step(step_id=4, deps=[2])
        sc = builder.build(
            step=step,
            step_outputs={1: "out-1", 2: "out-2", 3: "out-3"},
        )
        assert [e.step_id for e in sc.entries] == [2]

    def test_chain_receives_required_previous_outputs_only(self, builder):
        step3 = make_step(step_id=3, deps=[2])
        sc = builder.build(step=step3, step_outputs={1: "out-1", 2: "out-2"})
        assert [e.step_id for e in sc.entries] == [2]
        assert "out-1" not in sc.to_plain_text()

    def test_plain_text_format_matches_legacy_wire_format(self, builder):
        step = make_step(step_id=3, deps=[1, 2])
        sc = builder.build(step=step, step_outputs={1: "foo", 2: "bar"})
        assert sc.to_plain_text() == "[Step 1]\nfoo\n\n[Step 2]\nbar"


# ── Test 3: Missing / failed dependency ───────────────────────────────────────

class TestMissingFailedDependency:
    def test_missing_output_skipped(self, builder):
        step = make_step(step_id=2, deps=[1])
        sc = builder.build(step=step, step_outputs={})
        assert sc.entries == []
        assert sc.to_plain_text() == ""

    def test_empty_output_skipped(self, builder):
        step = make_step(step_id=2, deps=[1])
        sc = builder.build(step=step, step_outputs={1: ""})
        assert sc.entries == []

    def test_failed_dependency_never_propagates(self, builder):
        step = make_step(step_id=3, deps=[1, 2])
        sc = builder.build(
            step=step,
            step_outputs={1: "completed-out", 2: "failed-out"},
            step_status={1: "completed", 2: "failed"},
        )
        assert [e.step_id for e in sc.entries] == [1]

    def test_no_status_map_propagates_by_default(self, builder):
        step = make_step(step_id=2, deps=[1])
        sc = builder.build(step=step, step_outputs={1: "out"})
        assert [e.step_id for e in sc.entries] == [1]


# ── Test 4: Bounded propagation + safe truncation ─────────────────────────────

class TestTruncation:
    def test_oversized_output_truncated_metadata_kept(self):
        b = StepContextBuilder(max_output_chars=100)
        big = "x" * 300
        sc = b.build(
            step=make_step(step_id=2, deps=[1]),
            step_outputs={1: big},
            execution_id="exe-1",
        )
        entry = sc.entries[0]
        assert entry.truncated is True
        assert len(entry.output) == 100
        assert entry.origin_length == 300
        assert entry.step_id == 1
        assert entry.execution_id == "exe-1"
        assert sc.total_chars() == 100

    def test_undersized_output_untouched(self, builder):
        sc = builder.build(
            step=make_step(step_id=2, deps=[1]),
            step_outputs={1: "small"},
        )
        entry = sc.entries[0]
        assert entry.truncated is False
        assert entry.output == "small"
        assert entry.origin_length == 5

    def test_exact_bound_not_truncated(self):
        b = StepContextBuilder(max_output_chars=100)
        sc = b.build(step=make_step(step_id=2, deps=[1]), step_outputs={1: "y" * 100})
        assert sc.entries[0].truncated is False

    def test_truncated_text_renders_safely(self):
        b = StepContextBuilder(max_output_chars=10)
        sc = b.build(
            step=make_step(step_id=2, deps=[1]),
            step_outputs={1: "abcdefghijklmnop"},
        )
        assert sc.to_plain_text() == "[Step 1]\nabcdefghij"
        assert len(sc.to_plain_text()) == 10 + len("[Step 1]\n")


# ── Test 5: Lineage preservation ──────────────────────────────────────────────

class TestLineage:
    def test_lineage_retains_step_and_execution_ids(self, builder):
        step = make_step(step_id=3, deps=[1, 2])
        sc = builder.build(
            step=step,
            step_outputs={1: "out-1", 2: "out-2"},
            execution_id="exe-9",
        )
        lineage = sc.lineage()
        assert lineage == [
            {"step_id": 1, "execution_id": "exe-9", "session_id": "",
             "truncated": False, "origin_length": 5, "output_length": 5},
            {"step_id": 2, "execution_id": "exe-9", "session_id": "",
             "truncated": False, "origin_length": 5, "output_length": 5},
        ]

    def test_lineage_survives_truncation(self):
        b = StepContextBuilder(max_output_chars=50)
        sc = b.build(
            step=make_step(step_id=2, deps=[1]),
            step_outputs={1: "q" * 200},
            execution_id="exe-t",
        )
        assert sc.lineage()[0]["step_id"] == 1
        assert sc.lineage()[0]["execution_id"] == "exe-t"
        assert sc.lineage()[0]["truncated"] is True
        assert sc.lineage()[0]["origin_length"] == 200

    def test_step_context_to_dict_includes_entries(self, builder):
        sc = builder.build(
            step=make_step(step_id=2, deps=[1]),
            step_outputs={1: "out"},
            execution_id="exe-d",
        )
        d = sc.to_dict()
        assert d["step_id"] == 2
        assert len(d["entries"]) == 1
        assert d["entries"][0]["output_length"] == 3


# ── Test 6: Executor integration ──────────────────────────────────────────────

class TestExecutorIntegration:
    def _run(self, executor, step, ctx, step_outputs, step_status):
        captured = {}

        def fake_handler(step, context_str, pipeline_ctx, tool_selection=None):
            captured["context"] = context_str
            return "handled"

        from unittest import mock

        from app.agent.pipeline import executor as executor_module

        with mock.patch.dict(executor_module._ACTION_HANDLERS, {"direct_answer": fake_handler}):
            result = executor.execute_one(
                step=step,
                context=ctx,
                step_outputs=step_outputs,
                step_status=step_status,
            )
        return result, captured

    def test_step_result_carries_structured_context_with_lineage(self, executor):
        plan = Plan(
            goal="chain",
            steps=[
                make_step(step_id=1, deps=[], action="direct_answer"),
                make_step(step_id=2, deps=[1], action="direct_answer"),
            ],
            requires_tools=False,
        )
        ctx = make_ctx()
        result, captured = self._run(
            executor, plan.steps[1], ctx,
            step_outputs={1: "first output"},
            step_status={1: "completed"},
        )

        assert result.step_id == 2
        assert result.status == "completed"
        assert result.step_context is not None
        assert result.step_context.request_id == "req-1"
        assert result.step_context.execution_id == "exe-1"
        assert result.step_context.session_id == "session-1"
        assert result.step_context.project_id == "project-1"
        assert [e.step_id for e in result.step_context.entries] == [1]
        assert captured["context"] == "[Step 1]\nfirst output"
        assert result.step_context.lineage()[0]["execution_id"] == "exe-1"

    def test_executor_context_isolates_unrelated_steps(self, executor):
        plan = Plan(
            goal="isolation",
            steps=[make_step(step_id=2, deps=[1], action="direct_answer")],
            requires_tools=False,
        )
        ctx = make_ctx()
        result, captured = self._run(
            executor, plan.steps[0], ctx,
            step_outputs={1: "dep output", 3: "unrelated output"},
            step_status={1: "completed", 3: "completed"},
        )
        assert "[Step 3]" not in captured["context"]
        assert "unrelated output" not in captured["context"]
        assert captured["context"] == "[Step 1]\ndep output"

    def test_executor_step_without_deps_receives_empty_context(self, executor):
        plan = Plan(
            goal="single",
            steps=[make_step(step_id=1, deps=[], action="direct_answer")],
            requires_tools=False,
        )
        ctx = make_ctx()
        result, captured = self._run(
            executor, plan.steps[0], ctx,
            step_outputs={5: "leak"},
            step_status={5: "completed"},
        )
        assert captured["context"] == ""
        assert result.step_context is not None
        assert result.step_context.entries == []

    def test_executor_step_context_reuses_agent_state_request_id(self, executor):
        plan = Plan(
            goal="ids",
            steps=[make_step(step_id=1, deps=[], action="direct_answer")],
            requires_tools=False,
        )
        ctx = make_ctx(request_id="req-from-state")
        result, _ = self._run(executor, plan.steps[0], ctx, step_outputs={}, step_status={})
        assert result.step_context.request_id == "req-from-state"

    def test_blocked_dependency_never_reaches_handler(self, executor):
        plan = Plan(
            goal="blocked",
            steps=[make_step(step_id=2, deps=[1], action="direct_answer")],
            requires_tools=False,
        )
        ctx = make_ctx()
        result, _ = self._run(
            executor, plan.steps[0], ctx,
            step_outputs={1: "partial"},
            step_status={1: "failed"},
        )
        assert result.status == "blocked"
        assert result.step_context is None


# ── Test 7: No second memory system ───────────────────────────────────────────

class TestNoSecondMemorySystem:
    def test_step_context_uses_no_persistence_or_memory_imports(self):
        from app.agent.pipeline import step_context as sc

        src = inspect.getsource(sc)
        assert "app.services" not in src
        assert "sqlite" not in src
        assert "redis" not in src
        assert "chromadb" not in src
        assert "faiss" not in src
        assert "sqlalchemy" not in src

    def test_step_context_pure_dataclasses_no_store(self):
        from app.agent.pipeline import step_context as sc

        assert isinstance(StepContextBuilder(), sc.StepContextBuilder)
        entry = sc.ContextEntry(step_id=1, output="o")
        assert entry.step_id == 1
        assert entry.to_dict()["output_length"] == 1


