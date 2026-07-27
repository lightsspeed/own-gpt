from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SourcePolicy(str, Enum):
    NONE = "none"
    KB = "kb"
    WEB = "web"
    MEMORY = "memory"
    ATTACHMENT = "attachment"
    HYBRID = "hybrid"
    REASONING = "reasoning"


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
    "You are in STRICT KNOWLEDGE BASE MODE.\n\n"
    "RULES:\n"
    "1. You MUST answer using ONLY the Retrieved Knowledge sections below.\n"
    "2. Every factual claim MUST end with the specific [Chunk N] that supports it.\n"
    "   Example: \"NLB operates at Layer 4 [Chunk 1] and handles millions of RPS [Chunk 2].\"\n"
    "3. Use DIFFERENT chunks for DIFFERENT claims. Do not cite the same chunk for everything.\n"
    "4. Extract ALL relevant points across ALL chunks. Do not cherry-pick.\n"
    "5. Do NOT add any facts, examples, or scenarios not present in the Retrieved Knowledge.\n"
    "6. If the Retrieved Knowledge does not cover a topic, respond with:\n"
    "   \"I couldn't find relevant information in the knowledge base for this question. "
    "The uploaded documents don't appear to contain details on this topic. "
    "Try rephrasing your question, or ask me to search the web instead.\"\n"
    "7. Do NOT use your pre-training knowledge. The Retrieved Knowledge is your only source.\n"
    "8. You must cite at least 1 chunk. Preferably cite 2+ different chunks to show breadth."
)

_WEB_DIRECTIVE = (
    "Answer using information from your web search results.\n"
    "Cite the specific source chunks with [Chunk N] notation.\n"
    "If a search result is used, cite it. If no source supports a claim, flag it as uncertain."
)

_MEMORY_DIRECTIVE = (
    "Answer based on the user's long-term memory and conversation history.\n"
    "You do not need to cite chunks, but indicate when information comes from memory."
)

_REASONING_DIRECTIVE = (
    "Answer using your own reasoning. No external sources are needed.\n"
    "Do not fabricate citations."
)

_DEFAULT_CONTRACTS: dict[SourcePolicy, CitationContract] = {
    SourcePolicy.KB: CitationContract(
        requires_evidence=True,
        min_evidence=1,
        max_evidence=10,
        allow_external_knowledge=False,
        temperature=0.0,
        system_directive=_KB_DIRECTIVE,
        on_unsupported="remove",
    ),
    SourcePolicy.WEB: CitationContract(
        requires_evidence=True,
        min_evidence=1,
        max_evidence=10,
        allow_external_knowledge=True,
        temperature=0.3,
        system_directive=_WEB_DIRECTIVE,
        on_unsupported="flag",
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
        min_evidence=1,
        max_evidence=20,
        allow_external_knowledge=False,
        temperature=0.0,
        system_directive="Answer using ONLY the attached document. Cite chunks with [Chunk N].",
    ),
    SourcePolicy.HYBRID: CitationContract(
        requires_evidence=True,
        min_evidence=1,
        max_evidence=15,
        allow_external_knowledge=True,
        temperature=0.2,
        system_directive=(
            "You are answering from MULTIPLE SOURCES (Retrieved Knowledge + your own knowledge).\n\n"
            "RULES:\n"
            "1. Every claim that comes from the Retrieved Knowledge MUST end with [Chunk N].\n"
            "2. Claims from your own knowledge should NOT have chunk citations.\n"
            "3. Extract all relevant points from the Retrieved Knowledge first.\n"
            "4. Clearly distinguish between source-based and knowledge-based claims.\n"
            "5. Format as: \"NLB handles 1M+ RPS [Chunk 1]. It also supports TCP health checks.\"\n"
            "   (first claim cited, second claim is from own knowledge, no citation needed)"
        ),
        on_unsupported="mark",
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