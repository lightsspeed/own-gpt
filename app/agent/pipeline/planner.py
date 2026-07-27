"""
Planner: Determines what information sources are needed to answer the user's question.

Runs after Intent Classification and before any retrieval.
Produces a SourcePolicy that drives tool selection and retrieval strategy.

The planner is intentionally lightweight — it translates the already-computed
intent + route into an explicit SourcePolicy. No LLM calls.
"""

from __future__ import annotations

import logging
from app.core.langsmith import traceable
from .intent import Intent, IntentResult
from .router import RouterResult, RouteDecision
from .source_policy import SourcePolicy, SourcePolicyResult

logger = logging.getLogger(__name__)

_POLICY_MAP: dict[Intent, SourcePolicy] = {
    Intent.GENERAL:   SourcePolicy.NONE,
    Intent.KNOWLEDGE: SourcePolicy.KB,
    Intent.WEB:       SourcePolicy.WEB,
    Intent.MEMORY:    SourcePolicy.MEMORY,
    Intent.CODING:    SourcePolicy.NONE,
    Intent.REASONING: SourcePolicy.NONE,
    Intent.TOOL:      SourcePolicy.NONE,
    Intent.UNKNOWN:   SourcePolicy.KB,
}


class Planner:
    """
    Maps intent + route decision to an explicit SourcePolicy.

    The planner is stateless and synchronous — it simply translates
    the pipeline's existing intent/route analysis into a policy declaration.
    """

    @traceable(name="planner", metadata={"stage": "planner"})
    def plan(self, intent: IntentResult, route: RouterResult) -> SourcePolicyResult:
        policy = _POLICY_MAP.get(intent.intent, SourcePolicy.NONE)

        sources_required: list[str] = []

        if policy == SourcePolicy.KB:
            sources_required.append("knowledge_base")
        elif policy == SourcePolicy.WEB:
            sources_required.append("web")
        elif policy == SourcePolicy.MEMORY:
            sources_required.append("memory")
        elif route.decision == RouteDecision.RETRIEVAL:
            if policy == SourcePolicy.NONE:
                policy = SourcePolicy.KB
            sources_required.append("knowledge_base")

        if route.decision == RouteDecision.WEB_SEARCH:
            if policy == SourcePolicy.KB:
                policy = SourcePolicy.HYBRID
                sources_required.append("web")
            elif policy == SourcePolicy.NONE:
                policy = SourcePolicy.WEB
                sources_required.append("web")

        reason = f"intent={intent.intent.value} route={route.decision.value} policy={policy.value}"

        result = SourcePolicyResult(
            policy=policy,
            reason=reason,
            sources_required=sources_required,
        )

        logger.info(
            "stage=planner policy=%s intent=%s route=%s sources=%s",
            policy.value,
            intent.intent.value,
            route.decision.value,
            sources_required,
        )
        return result