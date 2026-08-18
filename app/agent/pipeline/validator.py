"""
Stage 2e: Answer Validation & Grounding (V3.7)

Purpose: Validate the synthesized final answer for grounding, coherence, and
execution integrity BEFORE it leaves the pipeline. Runs immediately after
Synthesis and decides the FINAL ANSWER — on failure the pipeline returns a
safe clarification instead of an unreliable answer.

Key invariants:
  - Deterministic checks always run first (no LLM, no tools, no I/O).
  - LLM fallback is OPTIONAL and uses the existing build_llm boundary —
    no new LLM abstraction.
  - The validator NEVER executes tools, performs retrieval, or mutates state.
  - Malformed LLM output degrades to the deterministic result (never raises).
  - No auto-retry and no re-planning — validation is single-pass.
  - Internal errors never leak into the final answer.

Grounding policy (mirrors ContextOrchestrator, V3.6):
  - general / coding / reasoning  → grounding OPTIONAL (never rejected)
  - memory / knowledge / document / web → grounding REQUIRED
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import List, Optional

from app.core.llm_provider import build_llm  # eager for patching

logger = logging.getLogger(__name__)

SAFE_CLARIFICATION_MESSAGE = (
    "I don't have enough reliable evidence to answer that confidently."
)

_LLM_PROMPT = """You are a strict answer validator for a grounded RAG assistant.

Given a user question, a candidate answer, and the retrieved evidence, evaluate:
1. Groundedness — Is every factual claim in the answer supported by the evidence?
2. Adequacy — Is there enough evidence to answer the question confidently?

Return ONLY valid JSON — no markdown, no explanation:
{"grounded": true/false, "confidence": 0.0-1.0, "issues": ["..."], "missing_evidence": ["..."]}"""


@dataclass
class ValidationResult:
    """Structured verdict produced by AnswerValidator.validate()."""
    valid: bool
    grounded: bool
    confidence: float
    issues: List[str] = field(default_factory=list)
    missing_evidence: List[str] = field(default_factory=list)
    corrected_answer: Optional[str] = None


class AnswerValidator:
    """
    Validates the synthesized final answer before it is returned.

    Flow:
      1. Deterministic checks (always) — empty answer, grounding policy,
         failed/blocked steps, unusable execution output.
      2. Optional LLM escalation — only when deterministic passes AND the
         answer must be grounded; malformed output degrades to deterministic.

    The validator is pure: it never executes tools, retrieves, or re-plans.
    """

    def __init__(
        self,
        use_llm: bool = False,
        model_name: Optional[str] = None,
        llm: Optional[object] = None,
    ) -> None:
        self._use_llm = use_llm
        self._model_name = model_name
        self._llm = llm

    # ── Public API ─────────────────────────────────────────────────────────

    def validate(
        self,
        question: str,
        answer: str,
        context: Optional[object] = None,
        execution: Optional[object] = None,
    ) -> ValidationResult:
        """Validate an answer. Returns a structured ValidationResult."""
        result = self._deterministic(question, answer, context, execution)
        if not self._use_llm or not result.valid:
            return result
        llm_result = self._llm_check(
            question=question,
            answer=answer,
            context=context,
            deterministic=result,
        )
        return llm_result if llm_result is not None else result

    # ── Deterministic core (no LLM, no tools, no I/O) ──────────────────────

    def _deterministic(
        self,
        question: str,
        answer: str,
        context: Optional[object],
        execution: Optional[object],
    ) -> ValidationResult:
        issues: List[str] = []
        missing: List[str] = []

        text = (answer or "").strip()
        if not text:
            return ValidationResult(
                valid=False,
                grounded=False,
                confidence=0.0,
                issues=["The answer is empty."],
            )

        grounding_required = bool(
            context is not None and getattr(context, "grounding_required", False)
        )
        has_evidence = bool(
            getattr(context, "has_evidence", False)
            or getattr(context, "source_count", 0) > 0
        )

        grounded = True
        if grounding_required and not has_evidence:
            grounded = False
            issues.append("Answer is not grounded: no evidence was retrieved.")
            issues.append(
                "Answer may contain factual claims unsupported by retrieved evidence."
            )
            missing.append("Relevant source evidence")

        # Execution integrity — failures are FLAGGED, not auto-recovered.
        if execution is not None:
            status = getattr(execution, "status", None)
            step_results = getattr(execution, "step_results", None) or []
            failed = [r for r in step_results if getattr(r, "status", None) == "failed"]
            blocked = [r for r in step_results if getattr(r, "status", None) == "blocked"]
            if failed or status == "failed":
                issues.append("A required execution step failed.")
            if blocked or status == "blocked":
                issues.append("A required execution step was blocked.")
            if status == "completed":
                completed = [
                    r for r in step_results if getattr(r, "status", None) == "completed"
                ]
                if completed and not any(
                    (getattr(r, "output", "") or "").strip() for r in completed
                ):
                    issues.append("Execution completed but produced no usable output.")

        # Grounding policy: optional for general/coding/reasoning — never reject.
        if not grounding_required:
            return ValidationResult(
                valid=True,
                grounded=True,
                confidence=0.7,
                issues=issues,
                missing_evidence=missing,
            )

        return ValidationResult(
            valid=grounded,
            grounded=grounded,
            confidence=0.9 if grounded else 0.2,
            issues=issues,
            missing_evidence=missing,
        )

    # ── Optional LLM escalation ────────────────────────────────────────────

    def _llm_check(
        self,
        question: str,
        answer: str,
        context: Optional[object],
        deterministic: ValidationResult,
    ) -> Optional[ValidationResult]:
        """Optional deep check. Returns None on any failure → deterministic fallback."""
        try:
            llm = self._llm if self._llm is not None else build_llm(
                model=self._model_name, temperature=0, max_tokens=128
            )
            from langchain_core.messages import HumanMessage, SystemMessage

            evidence = ""
            if context is not None:
                to_prompt = getattr(context, "to_prompt_context", None)
                if callable(to_prompt):
                    evidence = to_prompt() or ""
                else:
                    evidence = str(getattr(context, "sources", []))

            response = llm.invoke([
                SystemMessage(content=_LLM_PROMPT),
                HumanMessage(
                    content=(
                        f"Question: {question}\n\n"
                        f"Answer: {answer}\n\n"
                        f"Evidence:\n{evidence[:6000]}"
                    )
                ),
            ])
            content = response.content
            if isinstance(content, list):
                content = "".join(
                    block.get("text", "") for block in content if isinstance(block, dict)
                )
            data = json.loads(str(content).strip())

            llm_grounded = bool(data.get("grounded", True))
            try:
                confidence = float(data.get("confidence", deterministic.confidence))
            except (TypeError, ValueError):
                confidence = deterministic.confidence
            confidence = max(0.0, min(1.0, confidence))

            raw_issues = data.get("issues", [])
            raw_missing = data.get("missing_evidence", [])
            issues = [str(i) for i in raw_issues] if isinstance(raw_issues, list) else []
            missing = (
                [str(m) for m in raw_missing] if isinstance(raw_missing, list) else []
            )

            grounding_required = bool(
                context is not None and getattr(context, "grounding_required", False)
            )
            grounded = llm_grounded
            valid = grounded if grounding_required else True

            return ValidationResult(
                valid=valid,
                grounded=grounded,
                confidence=confidence,
                issues=issues,
                missing_evidence=missing,
            )
        except Exception as exc:
            logger.warning("answer_validator_llm_failed error=%s", exc)
            return None