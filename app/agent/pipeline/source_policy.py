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
    "2. CITE SOURCES INLINE, ATTACHED TO CLAIMS: When you make a claim or state a fact that relies on a specific source, cite it with the exact `[Chunk N]` marker shown next to that source above (zero-based: `[Chunk 0]`, `[Chunk 3]`, ...). Place each marker immediately after the specific statement it supports — do not attach markers to whole paragraphs or bullet lists. A claim without a marker is treated as ungrounded. Only use indices that actually appear in the sources list above; never invent indices. When a single statement is supported by several sources, list all of their markers together at the end of that statement (e.g. `Statement text. [Chunk 1] [Chunk 4]`). Keep the prose clean and natural, with markers placed unobtrusively.\n"
    "3. CRITICAL THINKING & REASONING: If the user asks to compare two mismatched concepts or entities from completely different categories (e.g., an abstract cognitive process vs a specific human athlete), explicitly call out the category error/mismatch first, then bridge to any meaningful connection.\n"
    "4. Structure your response clearly using headers (`###`), bullet points, bold key terms, and code blocks where appropriate.\n"
    "5. STRICT GROUNDING: You MUST answer using ONLY the provided Knowledge Base documents below. If the provided documents do NOT contain information or documentation on the topic asked, do not invent, speculate, or fall back on general knowledge. Respond that the available material is insufficient, for example with: 'The uploaded documents do not provide enough information to answer this confidently.' and stop.\n"
    "6. NEVER cite web/memory/external sources for knowledge-base claims, and never import outside knowledge into a document-grounded answer."
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
        system_directive="Provide a comprehensive, detailed answer using the attached document. Cite every claim from the document with the exact `[Chunk N]` marker shown next to that source above (zero-based). Attach each marker to the specific claim it supports (place the marker immediately after the statement, not on whole paragraphs). If several sources support one statement, list their markers together at the end of that statement (e.g. `Statement text. [Chunk 1] [Chunk 3]`). If the attached document does not contain the information needed to answer, respond that the available material is insufficient rather than using general knowledge. Write clean, well-structured Markdown prose.",
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