from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List


@dataclass
class Claim:
    id: str
    text: str
    char_start: int
    char_end: int


_ITEM_RE = re.compile(r'(?:^|\n)\s*(?:\d+[\.\)]\s*|\*\s+|-\s+|•\s+)(.+?)(?=\n\s*(?:\d+[\.\)]\s*|\*\s+|-\s+|•\s+)|\Z)', re.DOTALL)

_SENTENCE_RE = re.compile(r'(?<!\d\.)(?<=[.!?])\s+(?=[A-Z])')


def _normalize(text: str) -> str:
    """Remove [Chunk N] annotations and trailing whitespace for cleaner claims."""
    return re.sub(r'\s*\[Chunk\s+\d+\]', '', text).strip()


class ClaimExtractor:
    """
    Extracts atomic claims from an LLM response.
    
    Strategy:
    1. First try to parse numbered/bullet list items (each is a claim).
    2. If no list detected, split by sentence boundaries.
    3. Skip very short fragments and citation-only text.
    """

    def extract(self, response_text: str) -> List[Claim]:
        claims: List[Claim] = []
        seen: set[str] = set()

        # Strategy 1: Numbered or bullet list items
        items = _ITEM_RE.findall(response_text)
        if items:
            for item in items:
                text = _normalize(item).strip()
                if len(text) < 10:
                    continue
                if text.lower() in seen:
                    continue
                seen.add(text.lower())
                idx = response_text.find(item)
                claims.append(Claim(
                    id=f"c{len(claims)}",
                    text=text,
                    char_start=idx if idx >= 0 else 0,
                    char_end=(idx + len(text)) if idx >= 0 else len(text),
                ))
            return claims

        # Strategy 2: Sentence-based splitting
        cleaned = _normalize(response_text)
        sentences = _SENTENCE_RE.split(cleaned)
        for sent in sentences:
            text = sent.strip()
            if len(text) < 15:
                continue
            if text.lower() in seen:
                continue
            seen.add(text.lower())
            idx = response_text.find(text)
            claims.append(Claim(
                id=f"c{len(claims)}",
                text=text,
                char_start=idx if idx >= 0 else 0,
                char_end=(idx + len(text)) if idx >= 0 else len(text),
            ))

        return claims