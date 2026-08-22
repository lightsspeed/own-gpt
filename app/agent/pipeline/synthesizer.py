"""
Stage 2d: Execution Result Synthesizer (V3.4)

Purpose: Convert the per-step ExecutionResult from V3.3 into a single
coherent, user-facing answer.

Key architectural invariants:
  - Synthesizer NEVER executes tools, modifies memory, performs retrieval,
    or creates a new planning loop.
  - For simple single-step cases, avoids unnecessary LLM calls (deterministic path).
  - For multi-step / heterogeneous results, uses the existing build_llm.
  - Never exposes internal tool names, stack traces, object IDs, or error internals.
  - Failure handling is graceful and user-friendly.

Synthesis routing:
  single completed direct_answer  →  return output directly (no LLM)
  single completed memory         →  deterministic confirmation template
  single completed web_search     →  format existing search output (no LLM)
  single completed knowledge/doc  →  format existing KB output (no LLM)
  partial / multi-step            →  LLM synthesis combining step outputs
  all failed / blocked            →  graceful failure message (no LLM)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from app.agent.pipeline.executor import ExecutionResult, StepResult
from app.agent.pipeline.planner import Plan, PlanStep
from app.agent.pipeline.context import RetrievedContext
from app.agent.pipeline.trace import record_trace
from app.agent.pipeline.cost import TokenBudget
from app.core.llm_provider import build_llm  # eager for patching

logger = logging.getLogger(__name__)


# ── Synthesis Models ─────────────────────────────────────────────────────────

@dataclass
class StepSummary:
    """Lightweight summary of one executed step included in SynthesisResult."""
    step_id: int
    action: str
    status: str
    output_preview: str = ""    # first 200 chars of output
    # V4.7: structured tool outcome for audit/synthesis transparency.
    tool_status: str = ""       # completed | failed | blocked | empty | timeout
    error_code: Optional[str] = None


@dataclass
class SynthesisResult:
    answer: str
    success: bool
    used_execution_results: bool = True
    sources: list[str] = field(default_factory=list)
    step_summaries: list[StepSummary] = field(default_factory=list)


# ── Failure / partial-failure message helpers ────────────────────────────────

def _tool_outcome(r: StepResult) -> str:
    """Structured outcome of one step: step status, or ToolResult status
    when present (V4.7). Legacy steps without a ToolResult fall back to
    their step status, preserving historical synthesis behavior."""
    tr = getattr(r, "tool_result", None)
    if tr is not None:
        return getattr(tr, "status", r.status) or r.status
    return r.status


_FAILURE_MESSAGES: dict[str, str] = {
    "failed":  "I wasn't able to complete that step.",
    "blocked": "This step could not run because a required earlier step failed.",
}


def _graceful_failure(execution: ExecutionResult, plan: Plan) -> str:
    """Build a user-friendly explanation for all-failure or full-block outcomes.

    Distinguishes, from structured outcomes: failed action, timed-out
    action, empty (no usable result) action, and blocked action — never
    exposing internal codes, provider text, or tool names.
    """
    lines = []
    step_map: dict[int, PlanStep] = {s.step_id: s for s in plan.steps}
    for r in execution.step_results:
        step = step_map.get(r.step_id)
        action = step.action if step else "step"
        outcome = _tool_outcome(r)
        if outcome == "failed":
            lines.append(f"• The {action} step encountered an error.")
        elif outcome == "timeout":
            lines.append(f"• The {action} step timed out.")
        elif outcome == "empty":
            lines.append(f"• The {action} step returned no usable result.")
        elif outcome == "blocked":
            if r.status == "blocked":
                lines.append(
                    f"• The {action} step was skipped because an earlier step failed."
                )
            else:
                lines.append(
                    f"• The {action} step could not run because it was not permitted."
                )

    if lines:
        return (
            "I'm sorry, I wasn't able to complete your request:\n\n"
            + "\n".join(lines)
        )
    return "I'm sorry, I wasn't able to complete your request at this time."


def _format_memory_confirmation(output: str, question: str) -> str:
    """Return a natural confirmation for a memory storage result."""
    if "successfully" in output.lower() or "saved" in output.lower():
        return f"Got it — I've saved that to memory."
    if "denied" in output.lower() or "cannot" in output.lower():
        return f"I wasn't able to save that: {output}"
    return output


def _is_completed(r: StepResult) -> bool:
    return r.status == "completed"


# ── Synthesizer ───────────────────────────────────────────────────────────────

class Synthesizer:
    """
    V3.4 Execution Result Synthesizer.

    Converts ExecutionResult + Plan into a SynthesisResult (final user-facing answer).
    Does NOT execute tools, modify state, or re-plan.
    """

    _SYNTHESIS_SYSTEM = (
        "You are a helpful AI assistant. "
        "The following are results from several completed execution steps. "
        "Combine them into a single, natural, user-friendly response. "
        "Do not mention internal tool names, IDs, step numbers, or technical details. "
        "Do not fabricate information. "
        "Preserve all factual content from the step outputs."
    )

    def synthesize(
        self,
        question: str,
        plan: Plan,
        execution: ExecutionResult,
        context: object = None,
        retrieved_context: Optional[RetrievedContext] = None,
    ) -> SynthesisResult:
        """
        Synthesize a final user-facing answer from the execution result.

        Args:
            question: The original user question.
            plan:     The V3.2 Plan (for action/step metadata).
            execution: The V3.3 ExecutionResult containing StepResults.
            context:  PipelineContext (optional, for extra metadata).
            retrieved_context: Optional pre-retrieved context containing sources.

        Returns:
            SynthesisResult with `.answer`, `.success`, `.sources`, etc.
        """
        _synthesis_start = time.monotonic()
        agent_state = getattr(context, "agent_state", None)
        if agent_state:
            agent_state.synthesis_status = "running"
            logger.debug("agent.synthesis.started request_id=%s", agent_state.request_id)

        r_context = retrieved_context or getattr(context, "context", None)

        step_map: dict[int, PlanStep] = {s.step_id: s for s in plan.steps}
        completed = [r for r in execution.step_results if _is_completed(r)]
        failed    = [r for r in execution.step_results if r.status == "failed"]
        blocked   = [r for r in execution.step_results if r.status == "blocked"]
        total     = len(execution.step_results)

        # ── Step summaries for transparency ─────────────────────────────────
        summaries = [
            StepSummary(
                step_id=r.step_id,
                action=step_map[r.step_id].action if r.step_id in step_map else "unknown",
                status=r.status,
                output_preview=r.output[:200] if r.output else "",
                tool_status=getattr(getattr(r, "tool_result", None), "status", ""),
                error_code=getattr(getattr(r, "tool_result", None), "error_code", None),
            )
            for r in execution.step_results
        ]

        # Steps that "completed" at step level but produced no usable tool
        # outcome (V4.7: empty / timeout / blocked / failed ToolResult).
        non_usable = [
            r for r in completed
            if _tool_outcome(r) != "completed"
        ]

        # ── All steps failed / blocked ───────────────────────────────────────
        if not completed:
            answer = _graceful_failure(execution, plan)
            logger.info("synthesizer outcome=all_failed steps=%d", total)
            res = SynthesisResult(
                answer=answer,
                success=False,
                used_execution_results=True,
                sources=[],
                step_summaries=summaries,
            )
        # ── Single completed step — deterministic paths ──────────────────────
        elif len(completed) == 1 and total == 1:
            r = completed[0]
            step = step_map.get(r.step_id)
            action = step.action if step else "direct_answer"
            if _tool_outcome(r) != "completed":
                # Tool executed but produced nothing usable: no fabricated claim.
                answer = _graceful_failure(execution, plan)
                logger.info(
                    "synthesizer outcome=single_step_empty action=%s tool_status=%s",
                    action, _tool_outcome(r),
                )
                res = SynthesisResult(
                    answer=answer,
                    success=False,
                    used_execution_results=True,
                    sources=[],
                    step_summaries=summaries,
                )
            else:
                answer, sources = self._single_step_answer(action, r.output, question)
                if r_context and r_context.sources:
                    context_sources = [s.title for s in r_context.sources if s.source_type in ("knowledge", "document", "web")]
                    sources = list(set(sources + context_sources))
                logger.info("synthesizer outcome=single_step action=%s", action)
                res = SynthesisResult(
                    answer=answer,
                    success=True,
                    used_execution_results=True,
                    sources=sources,
                    step_summaries=summaries,
                )
        # ── Partial: some failed or blocked ─────────────────────────────────
        elif failed or blocked or non_usable:
            answer = self._partial_answer(
                completed, failed, blocked, step_map, question, non_usable
            )
            logger.info(
                "synthesizer outcome=partial completed=%d failed=%d blocked=%d non_usable=%d",
                len(completed), len(failed), len(blocked), len(non_usable),
            )
            sources = []
            if r_context and r_context.sources:
                sources = list(set([s.title for s in r_context.sources if s.source_type in ("knowledge", "document", "web")]))
            res = SynthesisResult(
                answer=answer,
                success=bool(completed),
                used_execution_results=True,
                sources=sources,
                step_summaries=summaries,
            )
        # ── All steps completed — LLM synthesis for multi-step ──────────────
        else:
            answer = self._llm_synthesize(question, completed, step_map, context=context)
            logger.info("synthesizer outcome=multi_step_synthesis steps=%d", len(completed))
            sources = []
            if r_context and r_context.sources:
                sources = list(set([s.title for s in r_context.sources if s.source_type in ("knowledge", "document", "web")]))
            res = SynthesisResult(
                answer=answer,
                success=True,
                used_execution_results=True,
                sources=sources,
                step_summaries=summaries,
            )

        if agent_state:
            agent_state.synthesis_status = "completed" if res.success else "failed"
            from app.agent.pipeline.state import finalize_timing
            finalize_timing(agent_state)
            logger.info("agent.request.completed %s", agent_state.summary())

        record_trace(
            context, "synthesis", "synthesis_completed",
            status="completed" if res.success else "failed",
            duration_ms=round((time.monotonic() - _synthesis_start) * 1000, 2),
            metadata={"success": res.success},
        )

        return res

    # ── Single-step deterministic answers ────────────────────────────────────

    def _single_step_answer(
        self, action: str, output: str, question: str
    ) -> tuple[str, list[str]]:
        """Return (answer, sources) for a single completed step without LLM."""
        if action == "direct_answer":
            return output, []

        if action == "memory":
            return _format_memory_confirmation(output, question), []

        if action in ("knowledge", "document"):
            # KB output already contains formatted context; return directly.
            # Sources extracted from "Source: <filename>" lines in the output.
            sources = self._extract_sources(output)
            return output, sources

        if action == "web_search":
            sources = self._extract_urls(output)
            return output, sources

        if action in ("coding", "reasoning"):
            return output, []

        # Fallback for any unknown single action
        return output, []

    # ── Partial-result answer (some succeeded, some failed/blocked) ──────────

    def _partial_answer(
        self,
        completed: list[StepResult],
        failed: list[StepResult],
        blocked: list[StepResult],
        step_map: dict[int, PlanStep],
        question: str,
        non_usable: Optional[list[StepResult]] = None,
    ) -> str:
        parts: list[str] = []

        # Confirmed completed steps
        for r in completed:
            step = step_map.get(r.step_id)
            action = step.action if step else "step"
            if action == "memory":
                parts.append(_format_memory_confirmation(r.output, question))
            elif action in ("direct_answer", "coding", "reasoning"):
                parts.append(r.output)
            elif action in ("knowledge", "document"):
                parts.append(r.output)
            elif action == "web_search":
                parts.append(r.output)
            else:
                parts.append(r.output)

        # Failed steps — user-friendly, no internal details
        for r in failed:
            step = step_map.get(r.step_id)
            action = step.action if step else "step"
            parts.append(
                f"Unfortunately, I couldn't complete the {action} part of your request."
            )

        # V4.7: completed steps whose tool outcome was empty/timeout — the
        # Agent must not silently present missing results as answers.
        for r in non_usable or []:
            step = step_map.get(r.step_id)
            action = step.action if step else "step"
            outcome = _tool_outcome(r)
            if outcome == "timeout":
                parts.append(
                    f"The {action} part of your request timed out."
                )
            elif outcome == "empty":
                parts.append(
                    f"I couldn't find any usable results for the {action} part of your request."
                )
            else:
                parts.append(
                    f"Unfortunately, the {action} part of your request did not complete."
                )

        # Blocked steps — dependency failure downstream
        for r in blocked:
            step = step_map.get(r.step_id)
            action = step.action if step else "step"
            parts.append(
                f"The {action} step was skipped because a required earlier step didn't complete."
            )

        return "\n\n".join(parts)

    # ── Multi-step LLM synthesis ─────────────────────────────────────────────

    def _llm_synthesize(
        self,
        question: str,
        completed: list[StepResult],
        step_map: dict[int, PlanStep],
        context: object = None,
    ) -> str:
        """Use existing build_llm to combine multiple completed step outputs.

        V4.9: when a TokenBudget is present and exhausted, the LLM call is
        SKIPPED and the deterministic concatenation fallback is used — no
        LLM call happens past the budget (graceful, never raises).
        """
        from langchain_core.messages import HumanMessage, SystemMessage

        # Build structured context from step outputs (ordered by step_id)
        context_parts = []
        for r in sorted(completed, key=lambda x: x.step_id):
            step = step_map.get(r.step_id)
            action = step.action if step else "step"
            context_parts.append(f"[{action.upper()} RESULT]\n{r.output}")

        context_str = "\n\n---\n\n".join(context_parts)
        user_msg = (
            f"Original request: {question}\n\n"
            f"Step outputs:\n\n{context_str}\n\n"
            "Please combine these into a single, natural response for the user."
        )

        def _fallback() -> str:
            return "\n\n".join(
                r.output for r in sorted(completed, key=lambda x: x.step_id)
            )

        try:
            # ── V4.9: budget gate BEFORE the LLM call ───────────────────────
            budget = None
            if context is not None:
                budget = getattr(context, "token_budget", None)
            if isinstance(budget, TokenBudget) and budget.check() is not None:
                logger.info("synthesizer_llm_skipped reason=budget_exhausted")
                return _fallback()

            llm = build_llm(temperature=0.3, max_tokens=1024)
            response = llm.invoke([
                SystemMessage(content=self._SYNTHESIS_SYSTEM),
                HumanMessage(content=user_msg),
            ])
            content = response.content
            if isinstance(content, list):
                content = "".join(
                    block.get("text", "") for block in content if isinstance(block, dict)
                )
            text = str(content).strip()

            # ── V4.9: account provider usage into the TokenBudget ───────────
            usage_meta = getattr(response, "usage_metadata", None)
            if isinstance(budget, TokenBudget) and isinstance(usage_meta, dict):
                model = getattr(llm, "model_name", "")
                if not isinstance(model, str):
                    model = ""
                budget.record(
                    model=model,
                    input_tokens=int(usage_meta.get("input_tokens", 0) or 0),
                    output_tokens=int(usage_meta.get("output_tokens", 0) or 0),
                )
            return text
        except Exception as exc:
            logger.warning("synthesizer_llm_failed error=%s", exc)
            # Graceful fallback: concatenate outputs
            return _fallback()

    # ── Source extraction helpers ─────────────────────────────────────────────

    @staticmethod
    def _extract_sources(text: str) -> list[str]:
        """Extract 'Source: <filename>' entries from KB output."""
        import re
        return re.findall(r"Source:\s*(.+)", text)

    @staticmethod
    def _extract_urls(text: str) -> list[str]:
        """Extract URLs from web search output."""
        import re
        return re.findall(r"URL:\s*(https?://\S+)", text)
