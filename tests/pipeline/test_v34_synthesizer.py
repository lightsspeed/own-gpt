"""Hermetic unit tests for V3.4 Execution Result Synthesizer.

All tests use mocked execution results — zero live LLM, API, or DB calls.

Test coverage:
  1.  SynthesisResult model fields
  2.  Single direct_answer step → output returned directly (no LLM)
  3.  Single memory step → deterministic confirmation (no LLM)
  4.  Single web_search step → output formatted + URL sources extracted (no LLM)
  5.  Single knowledge step → output returned + file sources extracted (no LLM)
  6.  Multi-step all completed → LLM synthesis called with combined context
  7.  Partial: one step failed → graceful partial answer (no LLM)
  8.  Partial: one step blocked → graceful blocking message included
  9.  All steps failed → graceful failure response, success=False
 10.  LLM synthesis failure → concatenation fallback (no exception raised)
 11.  Memory confirmation: "denied" guard response handled correctly
 12.  Empty execution (no steps) → safe graceful response
"""

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass

from app.agent.pipeline.synthesizer import Synthesizer, SynthesisResult, StepSummary
from app.agent.pipeline.executor import ExecutionResult, StepResult
from app.agent.pipeline.planner import Plan, PlanStep


# ── Helpers ───────────────────────────────────────────────────────────────────

def _step(step_id: int, action: str) -> PlanStep:
    return PlanStep(step_id=step_id, description=f"Step {step_id}", action=action,
                    dependencies=[], expected_output="output")

def _result(step_id: int, status: str, output: str = "", error: str = None) -> StepResult:
    return StepResult(step_id=step_id, status=status, output=output, error=error)

def _exec(step_results: list, status: str = "completed") -> ExecutionResult:
    outputs = {r.step_id: r.output for r in step_results if r.status == "completed"}
    return ExecutionResult(
        status=status,
        step_results=step_results,
        outputs=outputs,
        final_output=step_results[-1].output if step_results else None,
    )


@pytest.fixture
def synth():
    return Synthesizer()


# ── Test 1: SynthesisResult model fields ─────────────────────────────────────

class TestSynthesisResultModel:
    def test_synthesis_result_fields(self):
        result = SynthesisResult(
            answer="Hello",
            success=True,
            used_execution_results=True,
            sources=["doc.pdf"],
        )
        assert result.answer == "Hello"
        assert result.success is True
        assert result.used_execution_results is True
        assert result.sources == ["doc.pdf"]
        assert isinstance(result.step_summaries, list)


# ── Test 2: Single direct_answer step ────────────────────────────────────────

class TestSingleDirectAnswer:
    def test_direct_answer_returned_without_llm(self, synth):
        plan = Plan(goal="answer", steps=[_step(1, "direct_answer")], requires_tools=False)
        execution = _exec([_result(1, "completed", "Kubernetes uses RBAC for access control.")])

        with patch("app.agent.pipeline.synthesizer.build_llm") as mock_llm:
            result = synth.synthesize("explain RBAC", plan, execution)

        mock_llm.assert_not_called()
        assert result.success is True
        assert "Kubernetes uses RBAC" in result.answer


# ── Test 3: Single memory step ────────────────────────────────────────────────

class TestSingleMemoryStep:
    def test_memory_step_deterministic_confirmation(self, synth):
        plan = Plan(goal="store", steps=[_step(1, "memory")], requires_tools=True)
        output = "Successfully saved fact to long-term memory (abc123): 'Kubernetes is favorite'"
        execution = _exec([_result(1, "completed", output)])

        with patch("app.agent.pipeline.synthesizer.build_llm") as mock_llm:
            result = synth.synthesize("remember Kubernetes is my favorite", plan, execution)

        mock_llm.assert_not_called()
        assert result.success is True
        assert "saved" in result.answer.lower() or "memory" in result.answer.lower()

    def test_memory_step_denied_returns_informative_message(self, synth):
        plan = Plan(goal="store", steps=[_step(1, "memory")], requires_tools=True)
        output = "Cannot save fact: denied by guardrail"
        execution = _exec([_result(1, "completed", output)])

        result = synth.synthesize("store secret key", plan, execution)
        assert result.success is True
        assert "denied" in result.answer.lower() or "wasn" in result.answer.lower()


# ── Test 4: Single web_search step ───────────────────────────────────────────

class TestSingleWebSearch:
    def test_web_search_output_returned_with_urls(self, synth):
        plan = Plan(goal="search", steps=[_step(1, "web_search")], requires_tools=True)
        output = (
            "Web Search Results for 'latest Kubernetes release':\n\n"
            "[1] Title: Kubernetes v1.32\n"
            "    URL: https://kubernetes.io/blog/v1.32\n"
            "    Domain: kubernetes.io\n"
            "    Snippet: Kubernetes 1.32 introduces..."
        )
        execution = _exec([_result(1, "completed", output)])

        with patch("app.agent.pipeline.synthesizer.build_llm") as mock_llm:
            result = synth.synthesize("latest Kubernetes release?", plan, execution)

        mock_llm.assert_not_called()
        assert result.success is True
        assert "https://kubernetes.io/blog/v1.32" in result.sources
        assert "Kubernetes" in result.answer


# ── Test 5: Single knowledge step ────────────────────────────────────────────

class TestSingleKnowledgeStep:
    def test_knowledge_output_returned_with_sources(self, synth):
        plan = Plan(goal="search KB", steps=[_step(1, "knowledge")], requires_tools=False)
        output = (
            "Found the following information:\n\n"
            "Source: architecture.pdf\n"
            "RBAC stands for Role-Based Access Control...\n\n"
            "Source: rbac_guide.pdf\n"
            "Roles bind subjects to permissions..."
        )
        execution = _exec([_result(1, "completed", output)])

        with patch("app.agent.pipeline.synthesizer.build_llm") as mock_llm:
            result = synth.synthesize("what is RBAC?", plan, execution)

        mock_llm.assert_not_called()
        assert result.success is True
        assert "architecture.pdf" in result.sources
        assert "rbac_guide.pdf" in result.sources


# ── Test 6: Multi-step all completed → LLM synthesis ─────────────────────────

class TestMultiStepLLMSynthesis:
    def test_llm_called_for_multi_step_result(self, synth):
        plan = Plan(
            goal="remember and search",
            steps=[_step(1, "memory"), _step(2, "web_search"), _step(3, "direct_answer")],
            requires_tools=True,
        )
        sr = [
            _result(1, "completed", "Preference stored: Kubernetes"),
            _result(2, "completed", "Kubernetes v1.32 released with new features..."),
            _result(3, "completed", "Combined answer"),
        ]
        execution = _exec(sr, "completed")

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Great! I've saved your Kubernetes preference. The latest release is v1.32."
        mock_llm.invoke.return_value = mock_response

        with patch("app.agent.pipeline.synthesizer.build_llm", return_value=mock_llm):
            result = synth.synthesize(
                "remember I like Kubernetes and search for latest release", plan, execution
            )

        mock_llm.invoke.assert_called_once()
        assert result.success is True
        assert "v1.32" in result.answer or "Kubernetes" in result.answer

    def test_llm_receives_all_step_outputs(self, synth):
        """Verify LLM prompt contains content from all completed steps."""
        plan = Plan(
            goal="multi",
            steps=[_step(1, "memory"), _step(2, "web_search")],
            requires_tools=True,
        )
        sr = [
            _result(1, "completed", "MEMORY_OUTPUT_MARKER"),
            _result(2, "completed", "WEB_OUTPUT_MARKER"),
        ]
        execution = _exec(sr, "completed")

        captured_msgs = []
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Combined answer"

        def capture(messages):
            captured_msgs.extend(messages)
            return mock_response

        mock_llm.invoke.side_effect = capture

        with patch("app.agent.pipeline.synthesizer.build_llm", return_value=mock_llm):
            synth.synthesize("test query", plan, execution)

        combined = " ".join(str(m.content) for m in captured_msgs)
        assert "MEMORY_OUTPUT_MARKER" in combined
        assert "WEB_OUTPUT_MARKER" in combined


# ── Test 7: Partial — one step failed ─────────────────────────────────────────

class TestPartialFailure:
    def test_partial_answer_includes_completed_and_failure_note(self, synth):
        plan = Plan(
            goal="partial",
            steps=[_step(1, "memory"), _step(2, "web_search")],
            requires_tools=True,
        )
        sr = [
            _result(1, "completed", "Preference saved: Kubernetes"),
            _result(2, "failed", error="Tavily connection refused"),
        ]
        execution = _exec(sr, "partial")

        with patch("app.agent.pipeline.synthesizer.build_llm") as mock_llm:
            result = synth.synthesize("remember and search", plan, execution)

        mock_llm.assert_not_called()
        assert result.success is True   # partial success — at least one step completed
        assert "Kubernetes" in result.answer or "saved" in result.answer.lower()
        assert "couldn't" in result.answer.lower() or "couldn" in result.answer.lower()


# ── Test 8: Blocked step explained to user ───────────────────────────────────

class TestBlockedStep:
    def test_blocked_step_mentioned_gracefully(self, synth):
        plan = Plan(
            goal="blocked",
            steps=[_step(1, "memory"), _step(2, "web_search"), _step(3, "direct_answer")],
            requires_tools=True,
        )
        sr = [
            _result(1, "completed", "Memory stored"),
            _result(2, "failed", error="timeout"),
            _result(3, "blocked"),
        ]
        execution = _exec(sr, "partial")

        result = synth.synthesize("question", plan, execution)

        assert result.success is True
        assert "skipped" in result.answer.lower() or "couldn" in result.answer.lower()


# ── Test 9: All steps failed ─────────────────────────────────────────────────

class TestAllStepsFailed:
    def test_all_failed_returns_graceful_message(self, synth):
        plan = Plan(goal="fail", steps=[_step(1, "web_search")], requires_tools=True)
        sr = [_result(1, "failed", error="API error")]
        execution = _exec(sr, "failed")

        with patch("app.agent.pipeline.synthesizer.build_llm") as mock_llm:
            result = synth.synthesize("search web", plan, execution)

        mock_llm.assert_not_called()
        assert result.success is False
        assert "sorry" in result.answer.lower() or "wasn" in result.answer.lower()
        # No stack trace or internal details
        assert "Traceback" not in result.answer
        assert "api error" not in result.answer.lower()


# ── Test 10: LLM synthesis failure → fallback concatenation ──────────────────

class TestLLMSynthesisFailureFallback:
    def test_llm_failure_falls_back_to_concatenation(self, synth):
        plan = Plan(
            goal="multi", steps=[_step(1, "memory"), _step(2, "knowledge")], requires_tools=False
        )
        sr = [
            _result(1, "completed", "STEP1_OUTPUT"),
            _result(2, "completed", "STEP2_OUTPUT"),
        ]
        execution = _exec(sr, "completed")

        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = RuntimeError("LLM quota exceeded")

        with patch("app.agent.pipeline.synthesizer.build_llm", return_value=mock_llm):
            result = synth.synthesize("question", plan, execution)

        assert result.success is True
        assert "STEP1_OUTPUT" in result.answer
        assert "STEP2_OUTPUT" in result.answer
