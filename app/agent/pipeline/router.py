"""
Stage 2: Request Router

Purpose: Decide whether retrieval is needed based on intent.
         Prevents unnecessary vector search calls.

Routing table:
  knowledge → RETRIEVAL     (vector search needed)
  memory    → MEMORY        (memory store read/write, skip vector search)
  general   → DIRECT_LLM    (chitchat ONLY when rule-matched: greetings/thanks/arithmetic)
              RETRIEVAL     (LLM-classified "general" is informational — must be grounded)
  coding    → RETRIEVAL     (KB-only policy: answer only from knowledge base)
  reasoning → RETRIEVAL     (KB-only policy: answer only from knowledge base)
  tool      → DIRECT_LLM    (let agent decide which tool)
  unknown   → RETRIEVAL     (attempt retrieval, may help)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from app.core.langsmith import traceable
from .intent import Intent, IntentResult

logger = logging.getLogger(__name__)


class RouteDecision(str, Enum):
    RETRIEVAL     = "retrieval"
    MEMORY        = "memory"
    DIRECT_LLM    = "direct_llm"
    CLARIFICATION = "clarification"


@dataclass
class RouterResult:
    decision: RouteDecision
    skip_retrieval: bool
    reason: str


# ── Routing table ─────────────────────────────────────────────────────────────
_ROUTING_TABLE: dict[Intent, tuple[RouteDecision, bool]] = {
    Intent.KNOWLEDGE: (RouteDecision.RETRIEVAL,    False),
    Intent.MEMORY:    (RouteDecision.MEMORY,        True),
    Intent.GENERAL:   (RouteDecision.RETRIEVAL,    False),  # Rule-matched chitchat handled in route()
    Intent.CODING:    (RouteDecision.RETRIEVAL,    False),  # KB-only: refuse if not in knowledge base
    Intent.REASONING: (RouteDecision.RETRIEVAL,    False),  # KB-only: refuse if not in knowledge base
    Intent.TOOL:      (RouteDecision.DIRECT_LLM,   True),
    Intent.UNKNOWN:   (RouteDecision.RETRIEVAL,     False),  # Attempt retrieval for unknowns
}


class RequestRouter:
    """
    Stateless router — maps intent to a route decision.
    No LLM calls. No I/O.
    """

    @traceable(name="request_router", metadata={"stage": 2})
    def route(self, intent: IntentResult) -> RouterResult:
        # Rule-matched chitchat (greetings/thanks/arithmetic) is the ONLY
        # general query answered without retrieval. LLM-classified "general"
        # (pasted errors, vague statements) is informational — it must be
        # grounded in the knowledge base or refused.
        if intent.intent == Intent.GENERAL and intent.matched_rule == "GENERAL_CHAT":
            decision, skip = RouteDecision.DIRECT_LLM, True
        else:
            decision, skip = _ROUTING_TABLE.get(
                intent.intent,
                (RouteDecision.DIRECT_LLM, True),
            )

        result = RouterResult(
            decision=decision,
            skip_retrieval=skip,
            reason=f"intent={intent.intent.value} confidence={intent.confidence:.2f}",
        )

        logger.info(
            "stage=request_routing decision=%s skip_retrieval=%s",
            result.decision.value,
            result.skip_retrieval,
        )
        return result
