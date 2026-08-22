"""Tool guardrails — classify tool calls before execution.

Every tool call passes through a guardrail before anything runs. The guardrail
decides one of:

  - ALLOW            → safe to execute immediately (recorded for audit)
                        · read-only tools
                        · low-risk personalization (agent memory writes)
  - REQUIRE_APPROVAL → mutating/side-effectful, must wait for a human operator
  - DENY             → blocked outright (unknown tool, unsafe args)

Guardrails are deterministic rules. They never execute anything.
"""

from __future__ import annotations

import re
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


# Tool policy.
#   Read-only tools run automatically (no side effects).
#   Memory tools mutate agent memory but are low-risk chat personalization —
#   they auto-apply on the conversation side (ChatGPT-style UX), while every
#   call is still recorded as an auditable ToolExecution artifact.
#   Real side-effect tools (external integrations) require explicit human
#   approval per the platform constitution.
READ_ONLY_TOOLS = frozenset({"search_knowledge_base", "web_search"})
AUTO_TOOLS = frozenset({"remember_user_fact", "remember_session_fact", "forget_user_fact"})
MUTATING_TOOLS = frozenset({"sm_integration"})
DENY_TOOLS = frozenset()  # reserved for future dangerous tools

# Per-tool argument constraints
MAX_FACT_LENGTH = 500
ALLOWED_SM_TARGETS = frozenset({"twitter", "linkedin", "facebook", "instagram"})
ALLOWED_SM_ACTIONS = frozenset({"post", "read", "analyze"})

# Credential/secret token patterns — never persisted into memory (PII safety).
# Narrow by design: "secret" alone or "card" alone must not block innocent facts.
SECRET_PATTERNS = (
    r"\bpassword(s|es)?\b",
    r"\bpasswd\b",
    r"\bpwd\b",
    r"\bsecret\s+(key|answer|phrase|question|code|token)\b",
    r"\bapi[_\-\s]?key(s)?\b",
    r"\baccess[_\-\s]?token(s)?\b",
    r"\bpin\s*code\b",
    r"\b(credit|debit)\s+card\b",
    r"\bcard\s*(number|no\.?|num|cvv|expiry)\b",
    r"\bssn\b",
    r"\bpassport\b",
    r"sk-[a-zA-Z0-9]{20,}",
)

SECRET_TOOLS = frozenset({"remember_user_fact", "remember_session_fact", "forget_user_fact"})


def _validate_args(tool_name: str, args: dict) -> GuardrailDecision | None:
    """Return a DENY decision if arguments violate constraints, else None."""
    if tool_name in {"remember_user_fact", "remember_session_fact", "forget_user_fact"}:
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
        if tool_name in SECRET_TOOLS:
            lower = fact.lower()
            if any(re.search(p, lower) for p in SECRET_PATTERNS):
                return GuardrailDecision(
                    action=GuardrailAction.DENY,
                    tool_name=tool_name,
                    reason="memory must not contain credentials or secrets",
                )
    if tool_name in {"remember_session_fact", "forget_user_fact"}:
        session_id = str(args.get("session_id", "")).strip()
        if session_id and len(session_id) > 128:
            return GuardrailDecision(
                action=GuardrailAction.DENY,
                tool_name=tool_name,
                reason="session_id exceeds 128 chars",
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
    if tool_name not in READ_ONLY_TOOLS and tool_name not in AUTO_TOOLS and tool_name not in MUTATING_TOOLS:
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
    if tool_name in AUTO_TOOLS:
        return GuardrailDecision(
            GuardrailAction.ALLOW, tool_name, "low-risk memory personalization, auto-applied"
        )
    return GuardrailDecision(
        GuardrailAction.REQUIRE_APPROVAL, tool_name, "mutating tool requires operator approval"
    )
