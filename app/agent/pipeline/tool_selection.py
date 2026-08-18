"""Stage 2b+.2: Tool Selection & Argument Construction (V3.11)

Turns a V3.9 capability verdict into a concrete, validated tool call:

    CapabilitySelection (V3.9, authoritative)
            ↓
    ToolSelection — "this exact registered tool with these validated arguments"

Behavior:
  - Reuses registered tools ONLY (tool_gate.IMPL_FUNCS). NO new tools.
  - Per-action mapping:
        memory        → remember_user_fact / remember_session_fact
        web_search    → web_search
        knowledge     → search_knowledge_base
        document      → search_knowledge_base
        coding        → existing coding capability (LLM-based, no tool)
        reasoning     → direct LLM, no tool
        direct_answer → no tool
  - Arguments are constructed from PlanStep + question + PipelineContext:
        web_search             → {"query": "..."}
        search_knowledge_base  → {"query": "...", "project_id": "..."}
        remember_user_fact     → {"fact": "...", "user_id": "...", ...}
        remember_session_fact  → {"fact": "...", "session_id": "...", ...}
  - Validation before returning: capability must be allowed (V3.10), tool must
    be registered, required arguments must exist, basic types must be correct.
    Anything else fails closed with allowed=False.

Key invariants:
  - NEVER executes tools, never calls the tool gate, never calls an LLM.
  - V3.10 stays authoritative: a denied capability can NEVER get a tool here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from app.core.langsmith import traceable
from app.agent.pipeline.planner import Plan, PlanStep
from app.agent.pipeline.capabilities import CapabilitySelection, TOOL_ALIASES

logger = logging.getLogger(__name__)


# ── Outcome model ────────────────────────────────────────────────────────────

@dataclass
class ToolSelection:
    """Validated tool + arguments for one plan step. Never executes."""
    step_id: int
    tool: Optional[str] = None
    arguments: dict = field(default_factory=dict)
    allowed: bool = True
    reason: str = ""


# ── Per-action tool mapping (registered tools only) ─────────────────────────

_MEMORY_TOOLS = frozenset({"remember_user_fact", "remember_session_fact"})

_FIXED_TOOL_BY_ACTION: dict[str, str] = {
    "web_search": "web_search",
    "knowledge": "search_knowledge_base",
    "document": "search_knowledge_base",
}

_NO_TOOL_ACTIONS = frozenset({"coding", "reasoning", "direct_answer"})


# ── Argument helpers ─────────────────────────────────────────────────────────

def _arg_error(value, name: str) -> Optional[str]:
    """Return a deterministic validation error, or None when the value is OK."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return f"missing required argument '{name}'"
    if not isinstance(value, str):
        return f"invalid argument '{name}': must be a string"
    return None


class ToolSelector:
    """
    V3.11 tool selection layer.

    Pure decision layer: never executes tools, never calls the gate, never
    calls the LLM. Fully deterministic.
    """

    @staticmethod
    def _known_tools() -> frozenset[str]:
        from app.agent.tool_gate import IMPL_FUNCS
        return frozenset(IMPL_FUNCS.keys())

    @staticmethod
    def _denied(step: PlanStep, tool: Optional[str], reason: str) -> ToolSelection:
        return ToolSelection(
            step_id=step.step_id,
            tool=tool,
            arguments={},
            allowed=False,
            reason=reason,
        )

    @staticmethod
    def _capability_for(step: PlanStep, cap_by_id: dict[int, CapabilitySelection]) -> Optional[CapabilitySelection]:
        return cap_by_id.get(step.step_id)

    # ── Argument construction per tool ───────────────────────────────────────

    def _args_for_memory(self, step: PlanStep, tool: str, context: object) -> tuple[Optional[dict], Optional[str]]:
        question = getattr(context, "question", "") or ""
        fact = step.description or question
        err = _arg_error(fact, "fact")
        if err:
            return None, err

        user_id = getattr(context, "user_id", None)
        project_id = getattr(context, "project_id", None)
        session_id = getattr(context, "session_id", None)

        args: dict = {"fact": fact}
        if user_id is not None and str(user_id).strip():
            args["user_id"] = str(user_id)
        if project_id is not None and str(project_id).strip():
            args["project_id"] = str(project_id)
        if tool == "remember_session_fact":
            err = _arg_error(session_id, "session_id")
            if err:
                return None, err
            args["session_id"] = str(session_id)
        return args, None

    def _args_for_search(self, step: PlanStep, tool: str, context: object) -> tuple[Optional[dict], Optional[str]]:
        question = getattr(context, "question", "") or ""
        final_query = getattr(context, "final_query", "") or ""
        query = final_query or question or step.description
        err = _arg_error(query, "query")
        if err:
            return None, err

        args: dict = {"query": query}
        if tool == "search_knowledge_base":
            project_id = getattr(context, "project_id", None)
            args["project_id"] = str(project_id) if project_id else ""
        return args, None

    # ── Step selection ───────────────────────────────────────────────────────

    def _select_step(
        self,
        step: PlanStep,
        context: object,
        cap_by_id: dict[int, CapabilitySelection],
    ) -> ToolSelection:
        # 1. Capability must be allowed (V3.10 stays authoritative).
        cap = cap_by_id.get(step.step_id)
        if cap is None:
            return self._denied(step, None, f"no capability selection for step {step.step_id}")
        if not cap.allowed:
            reason = cap.reason or "not allowed"
            return self._denied(step, None, f"capability denied: {reason}")

        # 2. Resolve the step's requested tool (alias-aware).
        step_tool: Optional[str] = None
        if step.tool:
            step_tool = TOOL_ALIASES.get(step.tool, step.tool)

        # 3. No-tool actions (coding / reasoning / direct_answer).
        if step.action in _NO_TOOL_ACTIONS:
            if step_tool is not None:
                return self._denied(
                    step, step_tool, f"action '{step.action}' does not use a tool"
                )
            return ToolSelection(
                step_id=step.step_id,
                tool=None,
                arguments={},
                allowed=True,
                reason=f"no tool required for {step.action}",
            )

        # 4. Memory actions — remember_user_fact / remember_session_fact.
        if step.action == "memory":
            if step_tool is not None:
                if step_tool not in self._known_tools():
                    return self._denied(
                        step, step_tool, f"tool '{step_tool}' is not registered"
                    )
                if step_tool not in _MEMORY_TOOLS:
                    return self._denied(
                        step, step_tool, f"tool '{step_tool}' not valid for memory"
                    )
            tool = step_tool or "remember_user_fact"
            args, err = self._args_for_memory(step, tool, context)
            if err:
                return self._denied(step, tool, err)
            return ToolSelection(
                step_id=step.step_id,
                tool=tool,
                arguments=args,
                allowed=True,
                reason=f"tool '{tool}' arguments validated",
            )

        # 5. Fixed-tool actions — web search / knowledge / document.
        tool = _FIXED_TOOL_BY_ACTION.get(step.action)
        if tool is None:
            return self._denied(step, step_tool, f"unknown action '{step.action}'")
        if step_tool is not None and step_tool != tool:
            return self._denied(
                step, step_tool, f"tool '{step_tool}' not valid for action '{step.action}'"
            )
        if tool not in self._known_tools():
            return self._denied(step, tool, f"tool '{tool}' is not registered")

        args, err = self._args_for_search(step, tool, context)
        if err:
            return self._denied(step, tool, err)
        return ToolSelection(
            step_id=step.step_id,
            tool=tool,
            arguments=args,
            allowed=True,
            reason=f"tool '{tool}' arguments validated",
        )

    @traceable(name="tool_selector", metadata={"stage": "2b+.2"})
    def select(
        self,
        plan: Optional[Plan],
        context: object = None,
        capability_selections: Optional[list[CapabilitySelection]] = None,
    ) -> list[ToolSelection]:
        """
        Produce a validated ToolSelection for every plan step.

        Pure decision layer — never executes anything.

        Args:
            plan: The Plan produced by the planner (may be None or empty).
            context: PipelineContext carrying question, user/project/session
                     IDs needed for argument construction.
            capability_selections: V3.9 selections (authoritative). Missing or
                     denied capability ⇒ the tool selection fails closed.
        """
        if plan is None or not plan.steps:
            return []

        cap_by_id: dict[int, CapabilitySelection] = {}
        if capability_selections is not None:
            cap_by_id = {s.step_id: s for s in capability_selections}

        selections = [
            self._select_step(step, context, cap_by_id)
            for step in sorted(plan.steps, key=lambda s: s.step_id)
        ]

        logger.info(
            "stage=tool_selector steps=%d allowed=%d rejected=%d",
            len(selections),
            sum(1 for s in selections if s.allowed),
            sum(1 for s in selections if not s.allowed),
        )
        return selections