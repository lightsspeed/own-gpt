"""
Stage 1: Intent Classification

Purpose: Determine the type of user request before any retrieval or tool use.

Supported intents:
  general      — casual chat, greetings, arithmetic, simple facts
  memory       — requests to store or recall personal facts
  knowledge    — general factual questions, concepts, technology comparisons
  web          — requests requiring fresh, current, or real-time web information
  document     — questions about specific uploaded or project documents
  coding       — requests to write, fix, or debug code/scripts
  reasoning    — complex multi-step reasoning, math derivations, or proofs
  multi_intent — requests combining multiple capabilities
  tool         — requests to perform an external action (legacy backward-compatibility)
  unknown      — cannot determine

Implementation strategy:
  1. Fast rule-based detection (regex) — <1ms, no LLM cost
  2. LLM fallback — only when rules are inconclusive

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
    GENERAL      = "general"
    MEMORY       = "memory"
    KNOWLEDGE    = "knowledge"
    WEB          = "web"
    DOCUMENT     = "document"
    CODING       = "coding"
    REASONING    = "reasoning"
    MULTI_INTENT = "multi_intent"
    TOOL         = "tool"
    UNKNOWN      = "unknown"


@dataclass
class IntentResult:
    intent: Intent
    confidence: float
    reason: str = ""
    latency_ms: float = 0.0
    used_llm: bool = False
    matched_rule: str = ""
    requires_tool: bool = False
    candidate_tools: list[str] = field(default_factory=list)
    reasoning: str = ""

    def __post_init__(self):
        if not self.reasoning and self.reason:
            self.reasoning = self.reason
        elif not self.reason and self.reasoning:
            self.reason = self.reasoning


# ── Rule-based patterns (checked in declared order) ──────────────────────────

class Rule(NamedTuple):
    name: str
    intent: Intent
    patterns: list[str]
    requires_tool: bool = False
    candidate_tools: list[str] = []


_RULES: list[Rule] = [
    # 0. Multi-intent patterns (must precede single-intent rules)
    Rule("MULTI_INTENT_COMBINED", Intent.MULTI_INTENT, [
        r"\b(remember|save|store)\b.{0,60}\band\b.{0,60}\b(search|find|check|look up|write|code)\b",
        r"\b(search|look up|read)\b.{0,60}\band\b.{0,60}\b(write|create|code|save|remember)\b",
        r"\b(document|pdf|report)\b.{0,60}\band\b.{0,60}\b(web|internet|latest|news|code)\b",
    ], requires_tool=True, candidate_tools=["tavily_search", "remember_user_fact", "python_interpreter"]),

    # 1. Memory facts
    Rule("MEMORY_FACTS", Intent.MEMORY, [
        r"\b(remember|memorize|store|save|don[\'']t forget)\b.{0,40}\b(this|that|my|me|it)\b",
        r"\bmy name is\b",
        r"\bi am\b.{0,30}\band\b.{0,30}\bi\b",
        r"\bforget\b.{0,20}\b(this|that|everything)\b",
        r"\bwhat do you (know|remember) about me\b",
        r"\bwhat('| i)?s my\b.{0,40}\b(\w+)\b",          # "what's my name" / "what is my favorite color"
        r"\b(do you|did you|have you) (remember|forgot(ten)?|noticed|known)\b",
        r"\bwhat (did|have) i (tell|say|told|shared|mentioned|said)( you)?\b",
        r"\bcall me\b.{0,20}\b(\w+)\b",                  # "call me Akhi"
        r"\bin (this|our) (conversation|chat|discussion)\b",   # "in this conversation" → context recall
        r"\bwhat (are|were|did|have) we\b",              # "what are we building here" / "what did we discuss"
    ], requires_tool=False, candidate_tools=["remember_user_fact", "remember_session_fact"]),

    # 2. Web search / fresh information
    Rule("WEB_SEARCH", Intent.WEB, [
        r"\b(latest|current|today[\'']s|real-time|recent|fresh|live)\b.{0,40}\b(news|weather|price|stock|update|release|info|version|event|score)\b",
        r"\b(search|look up|find|check)\b.{0,20}\b(web|online|google|internet|latest)\b",
        r"\bwhat happened today\b",
        r"\bcurrent (version|price|weather|status|rate) of\b",
    ], requires_tool=True, candidate_tools=["tavily_search"]),

    # 3. Document / uploaded file questions
    Rule("DOCUMENT_DOC", Intent.DOCUMENT, [
        r"\b(in|from|according to|based on)\b.{0,20}\b(document|file|pdf|report|paper|knowledge base|attachment)\b",
        r"\bwhat does.{0,30}(say|mention|state|describe)\b",
        r"\bsummar(ize|y).{0,20}\b(document|file|pdf|report|paper|knowledge base)\b",
        r"\bsearch (in|inside) (the|my|uploaded) (document|file|pdf)\b",
    ], requires_tool=False, candidate_tools=[]),

    # 4. Coding / debugging
    Rule("CODING_WRITE", Intent.CODING, [
        r"\b(write|create|generate|fix|debug|refactor|implement|build)\b.{0,30}\b(code|function|class|method|script|program|module|api)\b",
        r"\b(python|javascript|typescript|java|go|rust|c\+\+|sql|bash)\b.{0,20}\b(code|example|snippet|function|class)\b",
        r"\bhow (do i|to) (write|implement|code)\b",
        r"\b(create|write|build)\b.{0,20}\b(dockerfile|makefile|docker-compose)\b",
    ], requires_tool=True, candidate_tools=["python_interpreter"]),

    # 5. External tool actions
    Rule("TOOL_ACTION", Intent.TOOL, [
        r"\b(upload|send|post|email)\b.{0,20}\b(this|that|an?|the|my|file|document|attachment|message)\b",
        r"\b(deploy|publish|schedule)\b.{0,30}\b(app|service|task|workflow|job)\b",
    ], requires_tool=True, candidate_tools=[]),

    # 6. Reasoning / complex math
    Rule("REASONING_COMPLEX", Intent.REASONING, [
        r"\b(prove|proof|derive|calculate|compute|solve)\b.{0,60}\b(step|equation|formula|problem|math|even|odd|integer|proof)\b",
        r"\bif.{0,50}then.{0,50}(what|how|will)\b",
    ], requires_tool=False, candidate_tools=[]),

    # 7. General chat
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
    ], requires_tool=False, candidate_tools=[]),

    # 8. Knowledge / explanation catch-all
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
    ], requires_tool=False, candidate_tools=[]),
]


# ── Classifier ───────────────────────────────────────────────────────────────

class IntentClassifier:
    """
    Classifies user intent using rule-based detection first,
    falling back to the configured LLM only when rules are inconclusive.
    """

    _SYSTEM_PROMPT = """You are a precise intent classifier for an AI assistant.

Classify the user query into exactly one of these intents:
  general      — greetings (hi/hello/thanks/bye), arithmetic (2+2), or conversational filler ("how are you")
  memory       — requests to remember, store, or recall personal facts about the user ("my favorite color is blue", "what is my name")
  knowledge    — general factual questions, concept explanations, technology comparisons ("what is Kubernetes RBAC?")
  web          — requests requiring fresh, current, or real-time web information ("latest news", "today's weather", "current stock price")
  document     — questions explicitly asking about uploaded/project documents ("summarize the PDF", "in the uploaded report")
  coding       — requests to write, fix, refactor, or debug code/scripts ("write a python function to...")
  reasoning    — mathematical derivations, formal logic proofs, multi-step math problems ("prove that...", "solve 2x+5=15")
  multi_intent — requests combining multiple distinct capabilities (e.g., "remember X AND search the web for Y")

Return ONLY valid JSON with no markdown formatting:
{
  "intent": "<intent>",
  "confidence": <0.0-1.0>,
  "reasoning": "<short rationale>",
  "requires_tool": <true|false>,
  "candidate_tools": ["<tool_name>", ...]
}"""

    def __init__(self, model_name: str | None = None) -> None:
        self._model_name = model_name
        self._llm: object | None = None

    def _get_llm(self):
        if self._llm is None:
            from app.core.llm_provider import build_llm
            self._llm = build_llm(model=self._model_name, temperature=0, max_tokens=128)
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
                        reasoning=f"Rule match: {rule.name}",
                        latency_ms=0.0,
                        used_llm=False,
                        matched_rule=rule.name,
                        requires_tool=rule.requires_tool,
                        candidate_tools=list(rule.candidate_tools),
                    )
        return None

    def _llm_classify(self, query: str) -> IntentResult:
        """Calls the configured LLM for intent classification.

        The model may return malformed JSON; a parse failure degrades to
        intent=unknown with safe defaults, never an exception."""
        from langchain_core.messages import HumanMessage, SystemMessage

        try:
            response = self._get_llm().invoke([
                SystemMessage(content=self._SYSTEM_PROMPT),
                HumanMessage(content=query),
            ])
            content = response.content
            if isinstance(content, list):
                content = "".join(
                    block.get("text", "") for block in content if isinstance(block, dict)
                )
            # Strip markdown formatting if present
            cleaned = content.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```[a-z]*\n?", "", cleaned)
                cleaned = re.sub(r"\n?```$", "", cleaned).strip()

            data = json.loads(cleaned)
            raw_intent = str(data.get("intent", "unknown")).lower()
            try:
                intent_enum = Intent(raw_intent)
            except ValueError:
                intent_enum = Intent.UNKNOWN

            candidate_tools = data.get("candidate_tools", [])
            if not isinstance(candidate_tools, list):
                candidate_tools = []

            return IntentResult(
                intent=intent_enum,
                confidence=float(data.get("confidence", 0.5)),
                reason=data.get("reasoning") or data.get("reason", "LLM classification"),
                reasoning=data.get("reasoning") or data.get("reason", "LLM classification"),
                latency_ms=0.0,
                used_llm=True,
                matched_rule="LLM_CLASSIFIER",
                requires_tool=bool(data.get("requires_tool", False)),
                candidate_tools=[str(t) for t in candidate_tools],
            )
        except Exception as exc:
            logger.warning("intent_llm_classification_failed error=%s", exc)
            return IntentResult(
                intent=Intent.UNKNOWN,
                confidence=0.4,
                reason="LLM returned unusable output",
                reasoning="LLM returned unusable output",
                latency_ms=0.0,
                used_llm=True,
                matched_rule="LLM_CLASSIFIER",
                requires_tool=False,
                candidate_tools=[],
            )

    # ── Public interface ─────────────────────────────────────────────────────

    def rule_classify(self, query: str) -> Optional[IntentResult]:
        """Rule-based intent classification only — deterministic, no LLM.

        Returns None when no rule matches. Used by consumers that must avoid
        non-deterministic classification (e.g. episodic memory filtering).
        """
        result = self._rule_classify(query)
        if result is None:
            return None
        result.latency_ms = 0.0
        return result

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
            "stage=intent_classification intent=%s confidence=%.2f used_llm=%s latency_ms=%.1f requires_tool=%s candidate_tools=%s",
            result.intent.value,
            result.confidence,
            result.used_llm,
            result.latency_ms,
            result.requires_tool,
            result.candidate_tools,
        )
        return result
