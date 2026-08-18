"""Hermetic unit tests for V3.5 Agent State, Execution Control & Observability.

All tests are fully mocked — zero live API, DB, or LLM calls.
"""

import time
import pytest
from unittest.mock import MagicMock, patch

from app.agent.pipeline.state import (
    AgentState,
    StepExecutionState,
    mark_step_started,
    mark_step_completed,
    mark_step_failed,
    mark_step_blocked,
    finalize_execution_status,
    finalize_timing,
)
from app.agent.pipeline.executor import Executor, ExecutionResult, StepResult
from app.agent.pipeline.planner import Plan, PlanStep
from app.agent.pipeline.pipeline import PipelineContext, RAGPipeline
from app.agent.pipeline.intent import Intent, IntentResult
from app.agent.pipeline.router import RequestRouter, RouterResult, RouteDecision
from app.agent.pipeline.source_policy import AnswerMode, SourcePolicy


# ── Test 1: AgentState initialization ────────────────────────────────────────

def test_agent_state_init():
    state = AgentState(request_id="req-123", question="What is Kubernetes?")
    assert state.request_id == "req-123"
    assert state.question == "What is Kubernetes?"
    assert state.intent is None
    assert state.route is None
    assert state.execution_status == "pending"
    assert state.synthesis_status is None
    assert isinstance(state.steps, list)
    assert len(state.steps) == 0
    assert state.started_at > 0


# ── Test 2: AgentState.to_dict() ─────────────────────────────────────────────

def test_agent_state_to_dict():
    state = AgentState(request_id="req-123", question="What is Kubernetes?")
    state.intent = "coding"
    state.route = "direct"
    state.steps = [StepExecutionState(step_id=1, status="completed", output="Output text", tool="some_tool")]
    d = state.to_dict()
    assert d["request_id"] == "req-123"
    assert d["intent"] == "coding"
    assert d["route"] == "direct"
    assert len(d["steps"]) == 1
    assert d["steps"][0]["step_id"] == 1
    assert d["steps"][0]["status"] == "completed"
    assert d["steps"][0]["output_preview"] == "Output text"
    assert d["steps"][0]["tool"] == "some_tool"


# ── Test 3: request ID propagation ───────────────────────────────────────────

def test_request_id_propagation():
    # Verify that during pipeline process, a unique request ID is generated and assigned
    # to AgentState, and survives in the PipelineContext.
    mock_vector_store = MagicMock()
    pipeline = RAGPipeline(vector_store=mock_vector_store, config={"intent_enabled": False, "rewrite_enabled": False})
    
    # Mock subprocess components so process() runs without throwing
    pipeline._planner = MagicMock()
    pipeline._planner.create_plan.return_value = Plan(goal="Test goal", steps=[], requires_tools=False)
    pipeline._planner.plan.return_value = AnswerMode.from_policy(SourcePolicy.NONE)
    
    pipeline._executor = MagicMock()
    pipeline._executor.execute.return_value = ExecutionResult(status="completed", step_results=[])
    
    pipeline._synthesizer = MagicMock()
    mock_synth_res = MagicMock()
    mock_synth_res.success = True
    pipeline._synthesizer.synthesize.return_value = mock_synth_res

    ctx = pipeline.process(question="hello", session_id="sess-1")
    assert ctx.agent_state is not None
    assert ctx.agent_state.request_id is not None
    assert len(ctx.agent_state.request_id) > 10


# ── Test 4: plan metadata propagation ────────────────────────────────────────

def test_plan_metadata_propagation():
    # Verify that plan details are propagated into AgentState.
    state = AgentState(request_id="req-1", question="hello")
    plan = Plan(
        goal="Test plan",
        steps=[
            PlanStep(step_id=1, description="step 1", action="memory", tool="remember_user_fact"),
            PlanStep(step_id=2, description="step 2", action="direct_answer")
        ],
        requires_tools=True
    )
    state.goal = plan.goal
    state.plan_steps = len(plan.steps)
    state.steps = [
        StepExecutionState(step_id=s.step_id, tool=s.tool, status="pending")
        for s in plan.steps
    ]

    assert state.goal == "Test plan"
    assert state.plan_steps == 2
    assert len(state.steps) == 2
    assert state.steps[0].step_id == 1
    assert state.steps[0].tool == "remember_user_fact"
    assert state.steps[0].status == "pending"


# ── Test 5: step starts as pending ───────────────────────────────────────────

def test_step_starts_as_pending():
    step = StepExecutionState(step_id=1)
    assert step.status == "pending"
    assert step.started_at is None
    assert step.completed_at is None
    assert step.duration_ms is None


# ── Test 6: step transition pending → running ────────────────────────────────

def test_step_transition_pending_to_running():
    state = AgentState(request_id="req-1", question="hello")
    state.steps = [StepExecutionState(step_id=1, status="pending")]
    
    with patch("time.perf_counter", side_effect=[100.0, 105.0]):
        mark_step_started(state, step_id=1, tool="web_search")
    
    assert state.steps[0].status == "running"
    assert state.steps[0].started_at == 100.0
    assert state.steps[0].tool == "web_search"
    assert state.current_step == 1
    assert state.execution_status == "running"


# ── Test 7: step transition running → completed ──────────────────────────────

def test_step_transition_running_to_completed():
    state = AgentState(request_id="req-1", question="hello")
    state.steps = [StepExecutionState(step_id=1, status="running", started_at=100.0)]
    
    with patch("time.perf_counter", return_value=102.5):
        mark_step_completed(state, step_id=1, output="Finished search")
        
    assert state.steps[0].status == "completed"
    assert state.steps[0].completed_at == 102.5
    assert state.steps[0].duration_ms == 2500.0  # (102.5 - 100.0) * 1000
    assert state.steps[0].output == "Finished search"


# ── Test 8: step failure records error ───────────────────────────────────────

def test_step_failure_records_error():
    state = AgentState(request_id="req-1", question="hello")
    state.steps = [StepExecutionState(step_id=1, status="running", started_at=100.0)]
    
    with patch("time.perf_counter", return_value=101.5):
        mark_step_failed(state, step_id=1, error="Tavily API 500")
        
    assert state.steps[0].status == "failed"
    assert state.steps[0].completed_at == 101.5
    assert state.steps[0].duration_ms == 1500.0
    assert state.steps[0].error == "Tavily API 500"


# ── Test 9: blocked dependency records blocked state ──────────────────────────

def test_blocked_dependency_records_blocked_state():
    state = AgentState(request_id="req-1", question="hello")
    state.steps = [
        StepExecutionState(step_id=1, status="failed"),
        StepExecutionState(step_id=2, status="pending")
    ]
    
    mark_step_blocked(state, step_id=2, reason="Dependency step 1 failed")
    assert state.steps[1].status == "blocked"
    assert state.steps[1].error == "Dependency step 1 failed"


# ── Test 10: step duration calculation ────────────────────────────────────────

def test_step_duration_calculation():
    step = StepExecutionState(step_id=1, status="running", started_at=50.0)
    state = AgentState(request_id="req-1", question="hello", steps=[step])
    with patch("time.perf_counter", return_value=50.042):
        mark_step_completed(state, step_id=1, output="ok")
    assert pytest.approx(step.duration_ms, 0.01) == 42.0


# ── Test 11: overall duration calculation ─────────────────────────────────────

def test_overall_duration_calculation():
    state = AgentState(request_id="req-1", question="hello", started_at=10.0)
    with patch("time.perf_counter", return_value=10.5):
        finalize_timing(state)
    assert state.completed_at == 10.5
    assert state.total_duration_ms == 500.0


# ── Test 12: all steps completed → execution_status=completed ─────────────────

def test_status_calculation_all_completed():
    state = AgentState(request_id="req-1", question="hello")
    state.steps = [
        StepExecutionState(step_id=1, status="completed"),
        StepExecutionState(step_id=2, status="completed")
    ]
    finalize_execution_status(state)
    assert state.execution_status == "completed"


# ── Test 13: partial execution → execution_status=partial ─────────────────────

def test_status_calculation_partial():
    state = AgentState(request_id="req-1", question="hello")
    state.steps = [
        StepExecutionState(step_id=1, status="completed"),
        StepExecutionState(step_id=2, status="failed")
    ]
    finalize_execution_status(state)
    assert state.execution_status == "partial"


# ── Test 14: all steps failed/blocked → execution_status=failed ───────────────

def test_status_calculation_all_failed():
    state = AgentState(request_id="req-1", question="hello")
    state.steps = [
        StepExecutionState(step_id=1, status="failed"),
        StepExecutionState(step_id=2, status="blocked")
    ]
    finalize_execution_status(state)
    assert state.execution_status == "failed"


# ── Test 15: synthesis lifecycle updates state ───────────────────────────────

def test_synthesis_lifecycle_updates_state():
    from app.agent.pipeline.synthesizer import Synthesizer
    synth = Synthesizer()
    
    plan = Plan(goal="test", steps=[PlanStep(step_id=1, description="step 1", action="direct_answer")], requires_tools=False)
    execution = ExecutionResult(
        status="completed",
        step_results=[StepResult(step_id=1, status="completed", output="Yes, RBAC is...")],
        outputs={1: "Yes, RBAC is..."}
    )
    
    state = AgentState(request_id="req-1", question="hello")
    class DummyContext:
        agent_state = state
    
    ctx = DummyContext()
    
    with patch("app.agent.pipeline.synthesizer.build_llm") as mock_llm:
        res = synth.synthesize("question", plan, execution, context=ctx)
        
    assert state.synthesis_status == "completed"
    assert state.completed_at is not None
    assert state.total_duration_ms >= 0.0


# ── Test 16: state survives through PipelineContext ──────────────────────────

def test_state_survives_through_pipeline_context():
    ctx = PipelineContext(question="hello", session_id="session-1")
    state = AgentState(request_id="req-abc", question="hello")
    ctx.agent_state = state
    assert ctx.agent_state.request_id == "req-abc"


# ── Test 17: invalid state transition is handled safely ────────────────────────

def test_invalid_state_transition_prevented():
    state = AgentState(request_id="req-1", question="hello")
    # Mark step as completed
    state.steps = [StepExecutionState(step_id=1, status="completed")]
    
    # Try to mark step as running again (invalid completed -> running transition)
    mark_step_started(state, step_id=1, tool="some_tool")
    
    # It should be ignored and status must remain "completed"
    assert state.steps[0].status == "completed"


# ── Test 18: summary does not expose full step outputs ────────────────────────

def test_summary_privacy():
    state = AgentState(request_id="req-1", question="hello")
    state.steps = [
        StepExecutionState(step_id=1, status="completed", output="CONFIDENTIAL_KEY_12345"),
        StepExecutionState(step_id=2, status="failed", error="SQL connection timed out at DB_PASSWORD")
    ]
    state.execution_status = "partial"
    state.total_duration_ms = 120.5
    
    summary_str = state.summary()
    
    # Summary should be clean
    assert "CONFIDENTIAL_KEY" not in summary_str
    assert "SQL connection" not in summary_str
    assert "DB_PASSWORD" not in summary_str
    assert "completed=1" in summary_str
    assert "failed=1" in summary_str
    assert "status=partial" in summary_str


# ── Test 19: no tool execution occurs inside the state layer ──────────────────

def test_no_tool_execution_in_state_layer():
    # Verify that the state module has no references to tool gate, tool implementations,
    # or RAG services.
    from app.agent.pipeline import state as state_module
    
    # We inspect state_module's imported names
    imported_names = dir(state_module)
    assert "request_tool_execution" not in imported_names
    assert "search_knowledge_base" not in imported_names
    assert "web_search" not in imported_names


# ── Test 20: existing V3.3 executor behavior remains compatible ──────────────

def test_executor_compatibility_without_state():
    # Running executor execute without passing agent_state context should complete safely
    executor = Executor()
    plan = Plan(
        goal="Direct answer plan",
        steps=[PlanStep(step_id=1, description="Hello", action="direct_answer")],
        requires_tools=False
    )
    
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "Response"
    mock_llm.invoke.return_value = mock_response
    
    with patch("app.agent.pipeline.executor.build_llm", return_value=mock_llm):
        result = executor.execute(plan, context=None)
        
    assert result.status == "completed"
    assert len(result.step_results) == 1
    assert result.step_results[0].output == "Response"
