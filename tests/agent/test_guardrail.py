"""Guardrail policy tests — tool classification for the agent gate.

Memory tools auto-apply (ChatGPT-style chat personalization); real
side-effect tools still require human approval.
"""

from __future__ import annotations

import pytest

from app.agent.guardrail import check_tool_call, GuardrailAction, MAX_FACT_LENGTH


def test_read_only_tool_allowed():
    decision = check_tool_call("search_knowledge_base", {"query": "nginx"})
    assert decision.action == GuardrailAction.ALLOW


def test_memory_tools_auto_allowed_without_approval():
    for tool in ("remember_user_fact", "remember_session_fact", "forget_user_fact"):
        decision = check_tool_call(tool, {"fact": "my name is akhi"})
        assert decision.action == GuardrailAction.ALLOW, tool


def test_session_memory_injects_session_id():
    decision = check_tool_call("remember_session_fact", {"fact": "x", "session_id": "sess-1"})
    assert decision.action == GuardrailAction.ALLOW


def test_side_effect_tool_still_requires_human_approval():
    decision = check_tool_call("sm_integration", {"action": "post", "target": "linkedin"})
    assert decision.action == GuardrailAction.REQUIRE_APPROVAL


def test_unregistered_tool_denied():
    decision = check_tool_call("rm_rf", {})
    assert decision.action == GuardrailAction.DENY


def test_empty_fact_denied():
    for tool in ("remember_user_fact", "forget_user_fact"):
        decision = check_tool_call(tool, {"fact": "   "})
        assert decision.action == GuardrailAction.DENY


def test_oversized_fact_denied():
    decision = check_tool_call("remember_user_fact", {"fact": "x" * (MAX_FACT_LENGTH + 1)})
    assert decision.action == GuardrailAction.DENY


def test_sm_target_allowlist_enforced():
    decision = check_tool_call("sm_integration", {"action": "post", "target": "myspace"})
    assert decision.action == GuardrailAction.DENY


@pytest.mark.parametrize("fact", [
    "my password is hunter2",
    "my credit card number is 4111111111111111",
    "my ssn is 123-45-6789",
    "remember my api key sk-proj-ABCDEF123456789",
    "my secret key is abcd1234",
])
def test_secrets_never_remembered(fact):
    decision = check_tool_call("remember_user_fact", {"fact": fact})
    assert decision.action == GuardrailAction.DENY
    assert "credential" in decision.reason


@pytest.mark.parametrize("fact", [
    "my favorite book is The Secret Garden",
    "I collect gift cards",
    "my bowling pin setup",
    "remember my favorite number is 42",
])
def test_innocent_facts_not_blocked_by_secret_scan(fact):
    decision = check_tool_call("remember_user_fact", {"fact": fact})
    assert decision.action == GuardrailAction.ALLOW