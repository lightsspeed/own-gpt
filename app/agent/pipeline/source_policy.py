"""
Source Policy: Explicit per-answer declaration of what information sources
were required to produce the response.

Each answer gets exactly one SourcePolicy:
  NONE       — LLM-only reply (greetings, math, simple facts, chitchat)
  KB         — Knowledge base retrieval used
  WEB        — Web search used
  MEMORY     — Personal memory recalled
  ATTACHMENT — Uploaded file used
  HYBRID     — Multiple sources combined (KB+Web, KB+Memory, etc.)
"""

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


@dataclass
class SourcePolicyResult:
    policy: SourcePolicy
    reason: str
    sources_required: list[str] = field(default_factory=list)