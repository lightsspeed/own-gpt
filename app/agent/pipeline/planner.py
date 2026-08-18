"""
Stage 2b: Agent Planner

Purpose: Build a structured execution plan (Plan model + PlanSteps)
defining WHAT needs to happen (goals, ordered steps, action types, dependencies,
tool requirements, and complexity estimates).

The planner is purely a decision layer — it NEVER executes tools or actions directly.
Execution is handled separately in subsequent agent/pipeline stages.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from app.core.langsmith import traceable
from .intent import Intent, IntentResult
from .router import RouterResult, RouteDecision
from .source_policy import SourcePolicy, AnswerMode

logger = logging.getLogger(__name__)


# ── Data Models ──────────────────────────────────────────────────────────────

@dataclass
class PlanStep:
    step_id: int
    description: str
    action: str  # "memory" | "knowledge" | "web_search" | "reasoning" | "coding" | "direct_answer"
    dependencies: list[int] = field(default_factory=list)
    expected_output: str = ""
    tool: Optional[str] = None


@dataclass
class Plan:
    goal: str
    steps: list[PlanStep]
    requires_tools: bool = False
    estimated_complexity: str = "simple"  # "simple" | "medium" | "complex"


_POLICY_MAP: dict[Intent, SourcePolicy] = {
    Intent.GENERAL:      SourcePolicy.NONE,
    Intent.KNOWLEDGE:    SourcePolicy.KB,
    Intent.DOCUMENT:     SourcePolicy.KB,
    Intent.MEMORY:       SourcePolicy.MEMORY,
    Intent.WEB:          SourcePolicy.NONE,
    Intent.CODING:       SourcePolicy.KB,
    Intent.REASONING:    SourcePolicy.KB,
    Intent.MULTI_INTENT: SourcePolicy.KB,
    Intent.TOOL:         SourcePolicy.NONE,
    Intent.UNKNOWN:      SourcePolicy.KB,
}


# ── Planner Implementation ──────────────────────────────────────────────────

class Planner:
    """
    Agent Planner — maps IntentResult + RouterResult into both an AnswerMode
    (for contract enforcement) and a structured Plan (for execution graph).

    Pure decision layer: never executes tools or accesses external I/O directly.
    """

    _LLM_PLANNER_PROMPT = """You are a precise task planner for an AI assistant.

Given a user query and its classified intent, produce a structured execution plan.

Supported step actions:
  memory        — store or recall personal facts about the user
  knowledge     — retrieve/read from knowledge base or uploaded document
  web_search    — search live web for real-time / current information
  coding        — write, refactor, or debug code
  reasoning     — solve math equations, proofs, or complex step-by-step logic
  direct_answer — synthesize final answer or handle simple chat/greetings

Return ONLY valid JSON with no markdown formatting:
{
  "goal": "<overall goal>",
  "estimated_complexity": "simple|medium|complex",
  "requires_tools": true|false,
  "steps": [
    {
      "step_id": 1,
      "description": "<step description>",
      "action": "<action>",
      "dependencies": [],
      "expected_output": "<expected output>",
      "tool": "<tool_name or null>"
    }
  ]
}"""

    def __init__(self, model_name: str | None = None) -> None:
        self._model_name = model_name
        self._llm: object | None = None

    def _get_llm(self):
        if self._llm is None:
            from app.core.llm_provider import build_llm
            self._llm = build_llm(model=self._model_name, temperature=0, max_tokens=256)
        return self._llm

    # ── Backward Compatible AnswerMode Plan ──────────────────────────────────

    @traceable(name="planner", metadata={"stage": "planner"})
    def plan(self, intent: IntentResult, route: RouterResult) -> AnswerMode:
        """Original contract method returning AnswerMode. Maintained for 100% backward compatibility."""
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

    # ── Structured Execution Plan Generation ─────────────────────────────────

    def _deterministic_plan(
        self, question: str, intent: IntentResult, route: RouterResult
    ) -> Optional[Plan]:
        """Generates deterministic single-step or rule-matched multi-step plan."""
        val = intent.intent.value if isinstance(intent.intent, Intent) else str(intent.intent)

        # 1. Single-step simple requests
        if val == Intent.GENERAL.value:
            return Plan(
                goal=f"Answer general conversational request: {question[:50]}",
                steps=[
                    PlanStep(
                        step_id=1,
                        description="Formulate direct conversational response",
                        action="direct_answer",
                        dependencies=[],
                        expected_output="Direct text answer",
                        tool=None,
                    )
                ],
                requires_tools=False,
                estimated_complexity="simple",
            )

        if val == Intent.MEMORY.value:
            tool_name = intent.candidate_tools[0] if intent.candidate_tools else None
            return Plan(
                goal=f"Process user memory request: {question[:50]}",
                steps=[
                    PlanStep(
                        step_id=1,
                        description="Recall or store user memory entity",
                        action="memory",
                        dependencies=[],
                        expected_output="Memory entity updated or retrieved",
                        tool=tool_name,
                    )
                ],
                requires_tools=intent.requires_tool,
                estimated_complexity="simple",
            )

        if val in (Intent.KNOWLEDGE.value, Intent.DOCUMENT.value):
            return Plan(
                goal=f"Answer question using knowledge base / document context: {question[:50]}",
                steps=[
                    PlanStep(
                        step_id=1,
                        description="Retrieve and synthesize relevant document context",
                        action="knowledge",
                        dependencies=[],
                        expected_output="Grounded factual answer with citations",
                        tool=None,
                    )
                ],
                requires_tools=False,
                estimated_complexity="simple",
            )

        if val == Intent.WEB.value:
            return Plan(
                goal=f"Search live web for current information: {question[:50]}",
                steps=[
                    PlanStep(
                        step_id=1,
                        description="Execute web search query for fresh information",
                        action="web_search",
                        dependencies=[],
                        expected_output="Search results with web source links",
                        tool="tavily_search",
                    )
                ],
                requires_tools=True,
                estimated_complexity="medium",
            )

        if val == Intent.CODING.value:
            return Plan(
                goal=f"Write or debug code for user request: {question[:50]}",
                steps=[
                    PlanStep(
                        step_id=1,
                        description="Generate or execute code snippet to solve request",
                        action="coding",
                        dependencies=[],
                        expected_output="Executable code block or execution result",
                        tool="python_interpreter" if intent.requires_tool else None,
                    )
                ],
                requires_tools=intent.requires_tool,
                estimated_complexity="medium",
            )

        if val == Intent.REASONING.value:
            return Plan(
                goal=f"Derive step-by-step reasoning or mathematical proof: {question[:50]}",
                steps=[
                    PlanStep(
                        step_id=1,
                        description="Formulate step-by-step logical derivation or calculation",
                        action="reasoning",
                        dependencies=[],
                        expected_output="Detailed step-by-step derivation",
                        tool=None,
                    )
                ],
                requires_tools=False,
                estimated_complexity="medium",
            )

        # 2. Rule-based multi-step planning for MULTI_INTENT requests
        if val == Intent.MULTI_INTENT.value:
            q_lower = question.lower()
            tools = intent.candidate_tools

            # Case A: Memory + Web Search
            if ("remember" in q_lower or "save" in q_lower or "store" in q_lower) and (
                "web" in q_lower or "search" in q_lower or "news" in q_lower or "latest" in q_lower
            ):
                return Plan(
                    goal=f"Store memory preference and search live web: {question[:50]}",
                    steps=[
                        PlanStep(
                            step_id=1,
                            description="Store user preference or fact to Memory V2",
                            action="memory",
                            dependencies=[],
                            expected_output="Memory stored",
                            tool="remember_user_fact",
                        ),
                        PlanStep(
                            step_id=2,
                            description="Execute web search for current information",
                            action="web_search",
                            dependencies=[1],
                            expected_output="Live web search results",
                            tool="tavily_search",
                        ),
                        PlanStep(
                            step_id=3,
                            description="Synthesize final response combining memory confirmation and web findings",
                            action="direct_answer",
                            dependencies=[1, 2],
                            expected_output="Combined final answer",
                            tool=None,
                        ),
                    ],
                    requires_tools=True,
                    estimated_complexity="complex",
                )

            # Case B: Memory + Coding
            if ("remember" in q_lower or "save" in q_lower) and (
                "code" in q_lower or "script" in q_lower or "python" in q_lower or "function" in q_lower
            ):
                return Plan(
                    goal=f"Store memory and generate code: {question[:50]}",
                    steps=[
                        PlanStep(
                            step_id=1,
                            description="Store user coding preference to Memory V2",
                            action="memory",
                            dependencies=[],
                            expected_output="Memory stored",
                            tool="remember_user_fact",
                        ),
                        PlanStep(
                            step_id=2,
                            description="Generate requested code implementation",
                            action="coding",
                            dependencies=[1],
                            expected_output="Generated code snippet",
                            tool="python_interpreter",
                        ),
                    ],
                    requires_tools=True,
                    estimated_complexity="complex",
                )

            # Case C: Knowledge/Document + Coding
            if ("document" in q_lower or "pdf" in q_lower or "file" in q_lower) and (
                "code" in q_lower or "script" in q_lower or "python" in q_lower
            ):
                return Plan(
                    goal=f"Retrieve document specification and implement code: {question[:50]}",
                    steps=[
                        PlanStep(
                            step_id=1,
                            description="Retrieve document specifications from Knowledge Base",
                            action="knowledge",
                            dependencies=[],
                            expected_output="Document specification context",
                            tool=None,
                        ),
                        PlanStep(
                            step_id=2,
                            description="Implement code adhering to retrieved specification",
                            action="coding",
                            dependencies=[1],
                            expected_output="Implemented code snippet",
                            tool="python_interpreter",
                        ),
                    ],
                    requires_tools=True,
                    estimated_complexity="complex",
                )

            # Fallback multi-intent plan if no explicit sub-rule matched
            return Plan(
                goal=f"Execute multi-intent request: {question[:50]}",
                steps=[
                    PlanStep(
                        step_id=1,
                        description="Execute primary capability step",
                        action="knowledge" if not tools else ("web_search" if "tavily_search" in tools else "memory"),
                        dependencies=[],
                        expected_output="Primary step result",
                        tool=tools[0] if tools else None,
                    ),
                    PlanStep(
                        step_id=2,
                        description="Synthesize final answer combining outputs",
                        action="direct_answer",
                        dependencies=[1],
                        expected_output="Synthesized multi-capability response",
                        tool=None,
                    ),
                ],
                requires_tools=bool(tools),
                estimated_complexity="complex",
            )

        return None

    def _llm_plan(self, question: str, intent: IntentResult) -> Plan:
        """LLM-assisted planning fallback for complex/unmatched queries."""
        from langchain_core.messages import HumanMessage, SystemMessage

        default_fallback = Plan(
            goal=f"Fulfill request: {question[:50]}",
            steps=[
                PlanStep(
                    step_id=1,
                    description="Process request and generate response",
                    action="direct_answer",
                    dependencies=[],
                    expected_output="Response text",
                    tool=None,
                )
            ],
            requires_tools=False,
            estimated_complexity="simple",
        )

        try:
            response = self._get_llm().invoke([
                SystemMessage(content=self._LLM_PLANNER_PROMPT),
                HumanMessage(content=f"Query: {question}\nIntent: {intent.intent.value}"),
            ])
            content = response.content
            if isinstance(content, list):
                content = "".join(
                    block.get("text", "") for block in content if isinstance(block, dict)
                )
            cleaned = content.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```[a-z]*\n?", "", cleaned)
                cleaned = re.sub(r"\n?```$", "", cleaned).strip()

            data = json.loads(cleaned)
            goal = str(data.get("goal", f"Fulfill request: {question[:50]}"))
            complexity = str(data.get("estimated_complexity", "medium"))
            if complexity not in ("simple", "medium", "complex"):
                complexity = "medium"
            requires_tools = bool(data.get("requires_tools", False))

            raw_steps = data.get("steps", [])
            if not isinstance(raw_steps, list) or not raw_steps:
                return default_fallback

            steps: list[PlanStep] = []
            for i, raw_s in enumerate(raw_steps, start=1):
                if not isinstance(raw_s, dict):
                    continue
                step_id = int(raw_s.get("step_id", i))
                desc = str(raw_s.get("description", f"Step {step_id}"))
                action = str(raw_s.get("action", "direct_answer"))
                raw_deps = raw_s.get("dependencies", [])
                deps = [int(d) for d in raw_deps if isinstance(d, (int, str)) and str(d).isdigit()]
                expected = str(raw_s.get("expected_output", ""))
                tool = raw_s.get("tool")
                if tool is not None:
                    tool = str(tool)

                steps.append(
                    PlanStep(
                        step_id=step_id,
                        description=desc,
                        action=action,
                        dependencies=deps,
                        expected_output=expected,
                        tool=tool,
                    )
                )

            if not steps:
                return default_fallback

            return Plan(
                goal=goal,
                steps=steps,
                requires_tools=requires_tools,
                estimated_complexity=complexity,
            )
        except Exception as exc:
            logger.warning("planner_llm_failed error=%s", exc)
            return default_fallback

    @traceable(name="agent_planner", metadata={"stage": "2b"})
    def create_plan(self, question: str, intent: IntentResult, route: RouterResult) -> Plan:
        """
        Creates a structured execution Plan for the user query.
        Uses deterministic rules first; falls back to LLM planning when inconclusive.

        Pure decision layer — NEVER executes tools or I/O.
        """
        plan = self._deterministic_plan(question, intent, route)
        if plan is None:
            plan = self._llm_plan(question, intent)

        logger.info(
            "stage=agent_planner goal=%r steps_count=%d complexity=%s requires_tools=%s",
            plan.goal,
            len(plan.steps),
            plan.estimated_complexity,
            plan.requires_tools,
        )
        return plan