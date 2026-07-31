"""
Stage 1: Intent Classification

Purpose: Determine the type of user request before any retrieval or tool use.

Supported intents:
  general   — casual chat, greetings, arithmetic, simple facts
  knowledge — questions about specific topics, concepts, or uploaded documents
  memory    — requests to store or recall personal facts
  tool      — requests to perform an external action
  coding    — requests to write, fix, or debug code
  reasoning — complex multi-step reasoning or math
  unknown   — cannot determine

Implementation strategy:
  1. Fast rule-based detection (regex) — <1ms, no LLM cost
  2. LLM fallback (gpt-4o-mini) — only when rules are insufficient

Performance targets:
  - Rule match:  <50ms
  - LLM fallback: <300ms
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import NamedTuple, Optional

from app.core.langsmith import traceable

logger = logging.getLogger(__name__)


# ── Supported intents ────────────────────────────────────────────────────────

class Intent(str, Enum):
    GENERAL   = "general"
    KNOWLEDGE = "knowledge"
    MEMORY    = "memory"
    TOOL      = "tool"
    CODING    = "coding"
    REASONING = "reasoning"
    UNKNOWN   = "unknown"


@dataclass
class IntentResult:
    intent: Intent
    confidence: float
    reason: str
    latency_ms: float
    used_llm: bool
    matched_rule: str = ""


# ── Rule-based patterns (checked in declared order) ──────────────────────────
# Named rules for provenance tracking — each Rule has a name, intent, and patterns.
# First match wins — order from most-specific to least-specific.

class Rule(NamedTuple):
    name: str
    intent: Intent
    patterns: list[str]


_RULES: list[Rule] = [
    Rule("MEMORY_FACTS", Intent.MEMORY, [
        r"\b(remember|memorize|store|save|don[\'']t forget)\b.{0,40}\b(this|that|my|me|it)\b",
        r"\bmy name is\b",
        r"\bi am\b.{0,30}\band\b.{0,30}\bi\b",
        r"\bforget\b.{0,20}\b(this|that|everything)\b",
        r"\bwhat do you (know|remember) about me\b",
    ]),
    Rule("CODING_WRITE", Intent.CODING, [
        r"\b(write|create|generate|fix|debug|refactor|implement|build)\b.{0,30}\b(code|function|class|method|script|program|module|api)\b",
        r"\b(python|javascript|typescript|java|go|rust|c\+\+|sql|bash)\b.{0,20}\b(code|example|snippet|function|class)\b",
        r"\bhow (do i|to) (write|implement|code)\b",
        r"\b(create|write|build)\b.{0,20}\b(dockerfile|makefile|docker-compose)\b",
    ]),
    Rule("KNOWLEDGE_DOC", Intent.KNOWLEDGE, [
        r"\b(in|from|according to|based on)\b.{0,20}\b(document|file|pdf|report|paper|knowledge base)\b",
        r"\bwhat does.{0,30}(say|mention|state|describe)\b",
        r"\bsummar(ize|y).{0,20}\b(document|file|pdf|report|paper|knowledge base)\b",
    ]),
    Rule("TOOL_ACTION", Intent.TOOL, [
        r"\b(upload|send|post|email)\b.{0,20}\b(this|that|an?|the|my|file|document|attachment|message)\b",
        r"\b(deploy|publish|schedule)\b.{0,30}\b(app|service|task|workflow|job)\b",
    ]),
    Rule("REASONING_COMPLEX", Intent.REASONING, [
        r"\b(prove|proof|derive|calculate|compute|solve)\b.{0,30}\b(step|equation|formula|problem|math)\b",
        r"\bif.{0,50}then.{0,50}(what|how|will)\b",
    ]),
    Rule("GENERAL_CHAT", Intent.GENERAL, [
        r"^(hello|hi|hey|howdy|greetings|sup|yo)\b",
        r"^(thanks|thank you|thx|ty|appreciate it)\b",
        r"^(goodbye|bye|see you|cya|later)\b",
        r"^(yes|no|ok|okay|sure|alright|fine|got it|understood)[\s!.,?]*$",
        r"^(good morning|good afternoon|good evening|good night)\b",
        r"^what is \d",                     # "what is 2+2"
        r"^\d[\d\s\+\-\*\/\(\)\.]+[\=\?]", # "5 * 3 ="
        r"^how are you",
        r"^who (are|r) you",
        r"^what (can|do) you do",
    ]),
    # Catch-all knowledge patterns — after specific rules so GENERAL/REASONING fire first.
    Rule("KNOWLEDGE_EXPLAIN", Intent.KNOWLEDGE, [
        r"\bexplain\b.{0,60}\b(\w+)\b",
        r"\bdescribe\b.{0,60}\b(\w+)\b",
        r"\btell me about\b.{0,60}\b(\w+)\b",
        r"\boverview of\b.{0,60}\b(\w+)\b",
        r"\bintroduction to\b.{0,60}\b(\w+)\b",
        r"\b(concept|architecture|lifecycle|benefits|best practices) of\b.{0,60}\b(\w+)\b",
        r"\bwhat (is|are)\b.{0,60}\b(\w+)\b",
        r"\bhow (does|do)\b.{0,60}\b(\w+)\b",
        r"\b(pros and cons|advantages and disadvantages|compare and contrast)\b",
        r"\bcompare\b.{0,80}\band\b.{0,80}\b\w+\b",       # "compare X and Y"
        r"\bdifference between\b.{0,60}\band\b",            # "difference between X and Y"
        r"\bvs\.?\b",                                       # "X vs Y"
    ]),
]


# ── Classifier ───────────────────────────────────────────────────────────────

class IntentClassifier:
    """
    Classifies user intent using rule-based detection first,
    falling back to a GPT-4o-mini call only when rules are inconclusive.
    """

    _SYSTEM_PROMPT = """You are a precise intent classifier for a RAG knowledge-base assistant.

Classify the user query into exactly one of these intents:
  general   — ONLY for: greetings (hi/hello/thanks/bye), arithmetic (2+2), or pure conversational filler ("how are you", "who are you")
  knowledge — ANY factual question, how-to, concept explanation, comparison between technologies/topics (e.g. "Kubernetes vs Docker Swarm"), pros/cons, tutorial, or topic-based query
  memory    — requests to remember, store, or recall personal facts about the user
  tool      — requests to perform a system action (post, send, email, create file, deploy)
  coding    — requests to write, fix, explain, or debug code/scripts
  reasoning — ONLY abstract mathematical derivations, formal logic proofs, or pure math puzzles (e.g. "solve 2x+5=15", "if A > B and B > C...")
  unknown   — cannot determine

IMPORTANT: All comparisons of concepts, tools, or technologies MUST be classified as knowledge. When in doubt, choose knowledge.

Return ONLY valid JSON — no explanation, no markdown:
{"intent": "<intent>", "confidence": <0.0-1.0>, "reason": "<10 words max>"}"""

    def __init__(self, model_name: str = "gpt-4o-mini") -> None:
        self._model_name = model_name
        self._llm: object | None = None  # lazy init to avoid import overhead at startup

    def _get_llm(self):
        if self._llm is None:
            from langchain_openai import ChatOpenAI
            self._llm = ChatOpenAI(model=self._model_name, temperature=0, max_tokens=64)
        return self._llm

    # ── Private helpers ──────────────────────────────────────────────────────

    def _rule_classify(self, query: str) -> Optional[IntentResult]:
        """Returns an IntentResult if a rule matches, else None."""
        q = query.lower().strip()
        for rule in _RULES:
            for pattern in rule.patterns:
                if re.search(pattern, q):
                    return IntentResult(
                        intent=rule.intent,
                        confidence=0.95,
                        reason=f"Rule: {rule.name}",
                        latency_ms=0.0,
                        used_llm=False,
                        matched_rule=rule.name,
                    )
        return None

    def _llm_classify(self, query: str) -> IntentResult:
        """Calls GPT-4o-mini for intent classification."""
        from langchain_core.messages import HumanMessage, SystemMessage

        response = self._get_llm().invoke([
            SystemMessage(content=self._SYSTEM_PROMPT),
            HumanMessage(content=query),
        ])
        data = json.loads(response.content.strip())
        return IntentResult(
            intent=Intent(data.get("intent", "unknown")),
            confidence=float(data.get("confidence", 0.5)),
            reason=data.get("reason", "LLM classification"),
            latency_ms=0.0,
            used_llm=True,
            matched_rule="LLM_CLASSIFIER",
        )

    # ── Public interface ─────────────────────────────────────────────────────

    @traceable(name="intent_classify", metadata={"stage": 1})
    def classify(self, query: str) -> IntentResult:
        """
        Classify intent. Rule-based first; LLM fallback if no rule matches.
        Always logs: intent, confidence, used_llm, latency_ms.
        """
        start = time.monotonic()

        result = self._rule_classify(query)
        if result is None:
            result = self._llm_classify(query)

        result.latency_ms = round((time.monotonic() - start) * 1000, 2)

        logger.info(
            "stage=intent_classification intent=%s confidence=%.2f used_llm=%s latency_ms=%.1f",
            result.intent.value,
            result.confidence,
            result.used_llm,
            result.latency_ms,
        )
        return result
