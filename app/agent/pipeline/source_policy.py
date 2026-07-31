from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SourcePolicy(str, Enum):
    NONE       = "none"
    KB         = "kb"
    MEMORY     = "memory"
    ATTACHMENT = "attachment"
    REASONING  = "reasoning"


@dataclass
class CitationContract:
    """Explicit contract for how an answer should handle sources."""
    requires_evidence: bool = False
    min_evidence: int = 0
    max_evidence: int = 10
    allow_external_knowledge: bool = True
    temperature: float = 0.7
    system_directive: str = ""
    on_unsupported: str = "keep"  # "remove" | "mark" | "flag" | "keep"


_KB_DIRECTIVE = (
    "You are an expert AI assistant answering questions using the provided Knowledge Base.\n\n"
    "GUIDELINES FOR YOUR RESPONSE:\n"
    "1. PROVIDE A DETAILED, COMPREHENSIVE, AND IN-DEPTH ANSWER using ONLY the provided Knowledge Base documents.\n"
    "2. DO NOT INCLUDE RAW `[Chunk N]` OR `[Chunk 0]` TAGS IN YOUR ANSWER TEXT. Write clean, natural, professional, and well-structured Markdown prose.\n"
    "3. CRITICAL THINKING & REASONING: If the user asks to compare two mismatched concepts or entities from completely different categories (e.g., an abstract cognitive process vs a specific human athlete), explicitly call out the category error/mismatch first, then bridge to any meaningful connection.\n"
    "4. Structure your response clearly using headers (`###`), bullet points, bold key terms, and code blocks where appropriate.\n"
    "5. STRICT GROUNDING: You MUST answer using ONLY the provided Knowledge Base documents below. If the provided documents do NOT contain information or documentation on the topic asked, state clearly and concisely that the topic is not covered in your knowledge base. DO NOT use general training knowledge or world knowledge to answer questions about unmentioned topics."
)

_MEMORY_DIRECTIVE = (
    "Answer based on the user's long-term memory and conversation history.\n"
    "Provide a natural, detailed, and helpful response."
)

_REASONING_DIRECTIVE = (
    "Answer using your own reasoning and analytical capabilities.\n"
    "Provide a step-by-step, thorough, and detailed response."
)

_DEFAULT_CONTRACTS: dict[SourcePolicy, CitationContract] = {
    SourcePolicy.KB: CitationContract(
        requires_evidence=True,
        min_evidence=0,
        max_evidence=10,
        allow_external_knowledge=True,
        temperature=0.2,
        system_directive=_KB_DIRECTIVE,
        on_unsupported="keep",
    ),
    SourcePolicy.MEMORY: CitationContract(
        requires_evidence=False,
        min_evidence=0,
        max_evidence=5,
        allow_external_knowledge=True,
        temperature=0.5,
        system_directive=_MEMORY_DIRECTIVE,
    ),
    SourcePolicy.ATTACHMENT: CitationContract(
        requires_evidence=True,
        min_evidence=0,
        max_evidence=20,
        allow_external_knowledge=False,
        temperature=0.2,
        system_directive="Provide a comprehensive, detailed answer using the attached document. Write clean Markdown prose without raw chunk labels.",
    ),
    SourcePolicy.REASONING: CitationContract(
        requires_evidence=False,
        min_evidence=0,
        max_evidence=0,
        allow_external_knowledge=True,
        temperature=0.7,
        system_directive=_REASONING_DIRECTIVE,
    ),
    SourcePolicy.NONE: CitationContract(
        requires_evidence=False,
        min_evidence=0,
        max_evidence=0,
        allow_external_knowledge=True,
        temperature=0.7,
        system_directive="Answer naturally. No citations needed.",
    ),
}


@dataclass
class AnswerMode:
    """Complete answer mode with policy, citation contract, and reasoning."""
    policy: SourcePolicy
    contract: CitationContract
    reason: str = ""
    sources_required: list[str] = field(default_factory=list)

    @classmethod
    def from_policy(cls, policy: SourcePolicy, reason: str = "",
                    sources_required: list[str] | None = None) -> AnswerMode:
        return cls(
            policy=policy,
            contract=_DEFAULT_CONTRACTS.get(policy, _DEFAULT_CONTRACTS[SourcePolicy.NONE]),
            reason=reason,
            sources_required=sources_required or [],
        )

    @classmethod
    def from_source_policy_result(cls, result, custom_directive: str | None = None) -> AnswerMode:
        mode = cls.from_policy(result.policy, result.reason, result.sources_required)
        if custom_directive:
            mode.contract.system_directive = custom_directive
        return mode