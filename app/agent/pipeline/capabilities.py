"""Stage 2b+: Capability Selection & Tool Matching (V3.9)

Maps every PlanStep.action to an existing registered platform capability and
its concrete tool, then verifies — deterministically, without executing —
that the capability is real, available, and permitted:

  1. The action maps to a known capability id (ACTION_CAPABILITY).
  2. The capability exists in the Capability Registry.
  3. The tool is registered in the tool gate (tool_gate.IMPL_FUNCS) and is
     not deny-listed by the guardrail.
  4. The source policy permits the capability (e.g. KB policy forbids web).
  5. Tool availability is configuration-driven (e.g. web requires
     TAVILY_API_KEY).

Key architectural invariants (mirrors the tool gate philosophy):
  - Never trust the planner blindly: an unknown action or an unregistered
    tool is rejected cleanly with `allowed=False` and reason
    "Capability is unavailable" — nothing is executed.
  - The selector NEVER executes tools, never calls a tool gate execution,
    never calls the LLM, never retrieves, and never introduces a new tool
    system. Selection is a pure decision layer.
  - Mutating tools (sm_integration) remain selectable but are marked as
    requiring operator approval — the tool gate still gates execution.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from app.core.langsmith import traceable
from app.agent.pipeline.planner import Plan, PlanStep
from app.agent.pipeline.source_policy import SourcePolicy
from app.agent.guardrail import MUTATING_TOOLS, DENY_TOOLS

logger = logging.getLogger(__name__)

_UNAVAILABLE = "Capability is unavailable"


# ── Outcome model ────────────────────────────────────────────────────────────

@dataclass
class CapabilitySelection:
    """Structured result of matching one PlanStep to a platform capability."""
    step_id: int
    capability: str
    tool: Optional[str] = None
    allowed: bool = True
    reason: str = ""


# ── Action → Capability mapping (existing registered capabilities only) ─────

ACTION_CAPABILITY: dict[str, str] = {
    "memory":        "memory_v2",        # governed memory store (services.memory)
    "knowledge":     "hybrid_retrieval", # RAG KB retrieval (agent.pipeline)
    "document":      "hybrid_retrieval", # uploaded documents are KB-scoped retrieval
    "web_search":    "tool_sandboxing",  # web executes through the guarded tool gate
    "coding":        "tool_sandboxing",  # code execution is sandboxed tool work
    "reasoning":     "answer_generation",  # LLM synthesis capability
    "direct_answer": "answer_generation",  # LLM synthesis capability
}

# Planner tool labels normalized to the tool gate's canonical tool names.
TOOL_ALIASES: dict[str, str] = {
    "tavily_search": "web_search",
}

# Actions denied per source policy (policy is enforced at selection time).
# SourcePolicy.NONE and an absent policy impose no restriction.
_POLICY_RESTRICTED_ACTIONS: dict[SourcePolicy, frozenset[str]] = {
    SourcePolicy.KB:         frozenset({"web_search"}),
    SourcePolicy.MEMORY:     frozenset({"web_search", "knowledge", "document"}),
    SourcePolicy.ATTACHMENT: frozenset({"web_search"}),
    SourcePolicy.REASONING:  frozenset({"web_search"}),
}


class CapabilitySelector:
    """
    V3.9 capability matching layer.

    Pure decision layer: never executes tools, never calls the LLM, and
    never performs retrieval. Selection is fully deterministic.
    """

    # ── Internal lookups (lazy imports keep tool_gate/settings out of
    #    module import time and allow hermetic test patching) ────────────────

    @staticmethod
    def _registry_get(cap_id: str):
        from app.learning.architecture import capabilities
        return capabilities.get(cap_id)

    @staticmethod
    def _known_tools() -> frozenset[str]:
        from app.agent.tool_gate import IMPL_FUNCS
        return frozenset(IMPL_FUNCS.keys())

    @staticmethod
    def _web_search_configured(tool_availability: Optional[dict]) -> bool:
        if tool_availability is not None:
            return bool(tool_availability.get("web_search", False))
        from app.core.config import settings
        return bool(getattr(settings, "TAVILY_API_KEY", None))

    @staticmethod
    def _policy_of(context: object) -> Optional[SourcePolicy]:
        """Extract the active SourcePolicy from a pipeline context if present."""
        mode = getattr(context, "source_policy", None) if context is not None else None
        if mode is None:
            return None
        if isinstance(mode, SourcePolicy):
            return mode
        return getattr(mode, "policy", None)

    # ── Step selection ───────────────────────────────────────────────────────

    def _select_step(
        self,
        step: PlanStep,
        context: object,
        tool_availability: Optional[dict],
    ) -> CapabilitySelection:
        # 1. Action must map to a known capability.
        cap_id = ACTION_CAPABILITY.get(step.action)
        if cap_id is None:
            return CapabilitySelection(
                step_id=step.step_id,
                capability=step.action,
                tool=step.tool,
                allowed=False,
                reason=_UNAVAILABLE,
            )

        # 2. Capability must exist in the Capability Registry.
        if self._registry_get(cap_id) is None:
            return CapabilitySelection(
                step_id=step.step_id,
                capability=cap_id,
                tool=step.tool,
                allowed=False,
                reason=_UNAVAILABLE,
            )

        # 3. Tool must be registered in the tool gate (after alias resolution).
        canonical: Optional[str] = step.tool
        if canonical is not None:
            canonical = TOOL_ALIASES.get(canonical, canonical)
            if canonical not in self._known_tools():
                return CapabilitySelection(
                    step_id=step.step_id,
                    capability=cap_id,
                    tool=step.tool,
                    allowed=False,
                    reason=_UNAVAILABLE,
                )
            if canonical in DENY_TOOLS:
                return CapabilitySelection(
                    step_id=step.step_id,
                    capability=cap_id,
                    tool=canonical,
                    allowed=False,
                    reason="tool is deny-listed",
                )

        # 4. Source policy must permit the capability.
        policy = self._policy_of(context)
        if policy is not None and policy != SourcePolicy.NONE:
            restricted = _POLICY_RESTRICTED_ACTIONS.get(policy, frozenset())
            if step.action in restricted:
                return CapabilitySelection(
                    step_id=step.step_id,
                    capability=cap_id,
                    tool=canonical,
                    allowed=False,
                    reason=f"{step.action} violates source policy {policy.value}",
                )

        # 5. Tool availability (configuration-driven).
        if step.action == "web_search" or canonical == "web_search":
            if not self._web_search_configured(tool_availability):
                return CapabilitySelection(
                    step_id=step.step_id,
                    capability=cap_id,
                    tool=canonical,
                    allowed=False,
                    reason="web search unavailable in current configuration",
                )

        # All checks passed — capability matched.
        if canonical is None:
            reason = f"capability {cap_id} available"
        elif canonical in MUTATING_TOOLS:
            reason = f"capability {cap_id} available; tool {canonical} requires operator approval"
        else:
            reason = f"capability {cap_id} available; tool {canonical} matched"

        return CapabilitySelection(
            step_id=step.step_id,
            capability=cap_id,
            tool=canonical,
            allowed=True,
            reason=reason,
        )

    @traceable(name="capability_selector", metadata={"stage": "2b+"})
    def select(
        self,
        plan: Optional[Plan],
        context: object = None,
        tool_availability: Optional[dict] = None,
    ) -> list[CapabilitySelection]:
        """
        Match every PlanStep to an existing, available, permitted capability.

        Deterministic. Never executes anything.

        Args:
            plan: The Plan produced by the planner (may be None or empty).
            context: Pipeline context carrying the active source policy
                     (attribute ``source_policy`` of type AnswerMode).
            tool_availability: Optional override mapping tool name → bool
                     (used to test configuration-driven availability without
                     touching real settings).
        """
        if plan is None or not plan.steps:
            return []

        selections = [
            self._select_step(step, context, tool_availability)
            for step in sorted(plan.steps, key=lambda s: s.step_id)
        ]

        logger.info(
            "stage=capability_selector steps=%d allowed=%d rejected=%d",
            len(selections),
            sum(1 for s in selections if s.allowed),
            sum(1 for s in selections if not s.allowed),
        )
        return selections