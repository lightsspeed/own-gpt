"""
Stage 8: Response Validation

Purpose: Validate the LLM response before returning it to the user.
         Reduce hallucinations and ensure answer quality.

Two-tier validation strategy — LLM is never called unless necessary:

Tier 1 — Rule Validation (no LLM, ~0ms):
  ✗ Empty or too-short response
  ✗ Duplicate paragraphs
  ✗ Unmatched code fences (odd number of ```)
  ✗ Response longer than 10,000 characters (likely runaway generation)

  → If ALL rules pass: validation is complete, response is served.
  → If ANY rule fails: escalate to Tier 2.

Tier 2 — LLM Validation (gpt-4o-mini, ~200-400ms):
  Only triggered when Tier 1 detects a problem.
  Checks:
  - Is the response relevant to the question?
  - Is the response grounded (no invented facts or APIs)?
  - Does the response contradict the provided context?
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass

from app.core.langsmith import traceable

logger = logging.getLogger(__name__)

_MAX_RESPONSE_LENGTH = 10_000
_MIN_RESPONSE_LENGTH = 5

_SYSTEM_PROMPT = """You are a strict response quality validator.

Given a user question and an AI response, evaluate:
1. Relevance — Is the response actually answering the question?
2. Groundedness — Does the response invent APIs, facts, or code that don't exist?
3. Contradiction — Does the response directly contradict what the question implies?

Return ONLY valid JSON — no markdown, no explanation:
{"valid": true/false, "reason": "<15 words max>"}"""


@dataclass
class ValidationResult:
    valid: bool
    reason: str
    used_llm: bool
    latency_ms: float


class ResponseValidator:
    """
    Two-tier response validator.
    Rule-based check is always performed first.
    LLM check only runs when rules detect a problem.
    """

    def __init__(self, model_name: str | None = None) -> None:
        # None resolves the provider default (LLM_MODEL under Ollama,
        # DEFAULT_MODEL under OpenAI) via the provider boundary.
        self._model_name = model_name
        self._llm: object | None = None

    def _get_llm(self):
        if self._llm is None:
            from app.core.llm_provider import build_llm
            self._llm = build_llm(model=self._model_name, temperature=0, max_tokens=64)
        return self._llm

    # ── Tier 1: Rule validation ──────────────────────────────────────────────

    def _rule_validate(self, response: str) -> tuple[bool, str]:
        """Returns (is_valid, reason). Fast, no LLM."""
        stripped = response.strip()

        if len(stripped) < _MIN_RESPONSE_LENGTH:
            return False, "Response is empty or too short"

        if len(stripped) > _MAX_RESPONSE_LENGTH:
            return False, "Response exceeds maximum length"

        # Duplicate paragraph check
        paragraphs = [p.strip() for p in stripped.split("\n\n") if p.strip()]
        if len(paragraphs) > 1 and len(set(paragraphs)) < len(paragraphs):
            return False, "Response contains duplicate paragraphs"

        # Unmatched code fences
        if response.count("```") % 2 != 0:
            return False, "Response has unmatched code fences"

        return True, "Rule validation passed"

    # ── Tier 2: LLM validation ───────────────────────────────────────────────

    def _llm_validate(self, question: str, response: str) -> tuple[bool, str]:
        """Returns (is_valid, reason). Uses the configured LLM.

        Malformed JSON from the model (possible with local models) degrades to
        "invalid" — the response stays flagged for review; never an exception."""
        from langchain_core.messages import HumanMessage, SystemMessage

        prompt = f"Question: {question[:500]}\n\nResponse: {response[:2000]}"
        try:
            result = self._get_llm().invoke([
                SystemMessage(content=_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ])
            data = json.loads(result.content.strip())
            return bool(data.get("valid", True)), data.get("reason", "LLM validation")
        except Exception as exc:
            logger.warning("llm_validation_failed error=%s", exc)
            return False, "LLM validation returned unusable output"

    # ── Public interface ─────────────────────────────────────────────────────

    @traceable(name="response_validator", metadata={"stage": 8})
    def validate(self, question: str, response: str) -> ValidationResult:
        """
        Validate the response. Rule-based first; LLM escalation only on failure.
        Logs: valid, used_llm, reason, latency_ms.
        """
        start = time.monotonic()
        used_llm = False

        valid, reason = self._rule_validate(response)

        if not valid:
            # Rule failed — escalate to LLM check
            valid, reason = self._llm_validate(question, response)
            used_llm = True

        elapsed = round((time.monotonic() - start) * 1000, 2)
        result = ValidationResult(
            valid=valid,
            reason=reason,
            used_llm=used_llm,
            latency_ms=elapsed,
        )

        logger.info(
            "stage=response_validation valid=%s used_llm=%s reason=%r latency_ms=%.1f",
            result.valid,
            result.used_llm,
            result.reason,
            result.latency_ms,
        )
        return result
