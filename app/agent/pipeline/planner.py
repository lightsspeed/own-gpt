from __future__ import annotations

import logging

from app.core.langsmith import traceable
from .intent import Intent, IntentResult
from .router import RouterResult, RouteDecision
from .source_policy import SourcePolicy, AnswerMode

logger = logging.getLogger(__name__)

_POLICY_MAP: dict[Intent, SourcePolicy] = {
    Intent.GENERAL:   SourcePolicy.NONE,
    Intent.KNOWLEDGE: SourcePolicy.KB,
    Intent.MEMORY:    SourcePolicy.MEMORY,
    Intent.CODING:    SourcePolicy.REASONING,
    Intent.REASONING: SourcePolicy.REASONING,
    Intent.TOOL:      SourcePolicy.NONE,
    Intent.UNKNOWN:   SourcePolicy.KB,
}


class Planner:
    """
    Maps intent + route decision to an explicit SourcePolicy + CitationContract.

    The planner is stateless and synchronous — it simply translates
    the pipeline's existing intent/route analysis into an AnswerMode.
    """

    @traceable(name="planner", metadata={"stage": "planner"})
    def plan(self, intent: IntentResult, route: RouterResult) -> AnswerMode:
        policy = _POLICY_MAP.get(intent.intent, SourcePolicy.NONE)

        sources_required: list[str] = []

        if policy == SourcePolicy.KB:
            sources_required.append("knowledge_base")
        elif policy == SourcePolicy.MEMORY:
            sources_required.append("memory")
        elif route.decision == RouteDecision.RETRIEVAL:
            if policy == SourcePolicy.NONE:
                policy = SourcePolicy.KB
            sources_required.append("knowledge_base")

        reason = f"intent={intent.intent.value} route={route.decision.value} policy={policy.value}"

        mode = AnswerMode.from_policy(
            policy=policy,
            reason=reason,
            sources_required=sources_required,
        )

        logger.info(
            "stage=planner policy=%s intent=%s route=%s sources=%s requires_evidence=%s",
            policy.value,
            intent.intent.value,
            route.decision.value,
            sources_required,
            mode.contract.requires_evidence,
        )
        return mode