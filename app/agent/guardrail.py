"""Tool guardrails — classify tool calls before execution.

Every tool call passes through a guardrail before anything runs. The guardrail
decides one of:

  - ALLOW         → read-only, safe to execute immediately
  - REQUIRE_APPROVAL → mutating/side-effectful, must wait for a human operator
  - DENY          → blocked outright (unknown tool, unsafe args)

Guardrails are deterministic rules. They never execute anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GuardrailAction(str, Enum):
    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    DENY = "deny"


@dataclass(frozen=True)
class GuardrailDecision:
    action: GuardrailAction
    tool_name: str
    reason: str = ""


# Tool policy — read-only tools run automatically; mutating tools require
# explicit human approval per the platform constitution.
READ_ONLY_TOOLS = frozenset({"search_knowledge_base"})
MUTATING_TOOLS = frozenset({"sm_integration", "remember_user_fact"})
DENY_TOOLS = frozenset()  # reserved for future dangerous tools

# Per-tool argument constraints
MAX_FACT_LENGTH = 500
ALLOWED_SM_TARGETS = frozenset({"twitter", "linkedin", "facebook", "instagram"})
ALLOWED_SM_ACTIONS = frozenset({"post", "read", "analyze"})


def _validate_args(tool_name: str, args: dict) -> GuardrailDecision | None:
    """Return a DENY decision if arguments violate constraints, else None."""
    if tool_name == "remember_user_fact":
        fact = str(args.get("fact", ""))
        if len(fact) > MAX_FACT_LENGTH:
            return GuardrailDecision(
                action=GuardrailAction.DENY,
                tool_name=tool_name,
                reason=f"fact exceeds {MAX_FACT_LENGTH} chars",
            )
        if not fact.strip():
            return GuardrailDecision(
                action=GuardrailAction.DENY,
                tool_name=tool_name,
                reason="fact must not be empty",
            )
    if tool_name == "sm_integration":
        target = str(args.get("target", "")).lower()
        action = str(args.get("action", "")).lower()
        if target not in ALLOWED_SM_TARGETS:
            return GuardrailDecision(
                action=GuardrailAction.DENY,
                tool_name=tool_name,
                reason=f"target '{target}' not in allowlist",
            )
        if action not in ALLOWED_SM_ACTIONS:
            return GuardrailDecision(
                action=GuardrailAction.DENY,
                tool_name=tool_name,
                reason=f"action '{action}' not in allowlist",
            )
    return None


def check_tool_call(tool_name: str, args: dict) -> GuardrailDecision:
    """Classify a tool call. Never executes anything."""
    if tool_name in DENY_TOOLS:
        return GuardrailDecision(GuardrailAction.DENY, tool_name, "tool is deny-listed")
    if tool_name not in READ_ONLY_TOOLS and tool_name not in MUTATING_TOOLS:
        return GuardrailDecision(
            GuardrailAction.DENY, tool_name, "tool is not registered in the guardrail policy"
        )

    violation = _validate_args(tool_name, args)
    if violation:
        return violation

    if tool_name in READ_ONLY_TOOLS:
        return GuardrailDecision(
            GuardrailAction.ALLOW, tool_name, "read-only tool, no side effects"
        )
    return GuardrailDecision(
        GuardrailAction.REQUIRE_APPROVAL, tool_name, "mutating tool requires operator approval"
    )
