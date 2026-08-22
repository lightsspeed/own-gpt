from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

from app.core.langsmith import traceable
from app.models.evidence import EvidenceItem, ConfidenceLabel, RetrievalMethod, confidence_from_score
from .reranker import RankedChunk
from .source_policy import SourcePolicy, AnswerMode

logger = logging.getLogger(__name__)


@dataclass
class EvidenceBuilderResult:
    evidence: list[EvidenceItem] = field(default_factory=list)
    source_policy: Optional[SourcePolicy] = None
    total_candidates: int = 0
    total_cited: int = 0
    total_validated: int = 0

    @property
    def debug_dict(self) -> dict:
        return {
            "total_candidates": self.total_candidates,
            "total_cited": self.total_cited,
            "total_validated": self.total_validated,
        }


_CHUNK_REF_RE = re.compile(r'\[Chunk\s+(\d+)\]', re.IGNORECASE)

# Bare [N] reference in a web-only answer (matches the tool's 1-based labels).
# Negative lookbehind excludes [Chunk N]; negative lookahead excludes markdown
# links like [1](https://...).
_WEB_BARE_REF_RE = re.compile(r'(?<!Chunk\s)\[(\d+)\](?!\()', re.IGNORECASE)


def _parse_chunk_references(response_text: str) -> list[int]:
    """Parse explicit [Chunk N] references from the LLM response."""
    indices = set()
    for match in _CHUNK_REF_RE.finditer(response_text):
        try:
            idx = int(match.group(1))
            if idx >= 0:
                indices.add(idx)
        except ValueError:
            continue
    return sorted(indices)


@dataclass
class WebCandidate:
    """A single structured web search result (parsed from the tool output)."""
    title: str
    url: str
    domain: str
    snippet: str
    label: int  # 1-based label as shown in the web tool output


_WEB_ITEM_BLOCK_RE = re.compile(
    r'\[(\d+)\]\s*Title:\s*(.+?)\s*\n\s*URL:\s*(\S+)(?:\s*\n\s*Domain:\s*(\S+))?(?:\s*\n\s*Snippet:\s*(.*?))?(?=\n\s*\[\d+\]\s|$|\Z)',
    re.IGNORECASE | re.DOTALL,
)


def parse_web_results(text: str) -> list[WebCandidate]:
    """Deterministically parse the web_search tool output into structured items.

    The tool emits a stable format (see tool_impls.web_search_impl):

        Web Search Results for 'query':

        [1] Title: Example
            URL: https://example.com
            Domain: example.com
            Snippet: snippet text

        [2] ...

    Returns the parsed items in display order. Never raises; malformed input
    yields an empty list.
    """
    items: list[WebCandidate] = []
    if not isinstance(text, str) or not text.strip():
        return items

    # Strip the leading "Web Search Results for '...':" header if present.
    body = re.sub(r'^Web\s+Search\s+Results\s+for\s+.*?:\s*', '', text.strip(), flags=re.IGNORECASE | re.DOTALL)

    for match in _WEB_ITEM_BLOCK_RE.finditer(body):
        try:
            label = int(match.group(1))
        except (ValueError, TypeError):
            continue
        title = (match.group(2) or "").strip()
        url = (match.group(3) or "").strip()
        domain = (match.group(4) or "").strip()
        snippet = (match.group(5) or "").rsplit("\n", 1)[0].strip() if match.group(5) else ""
        if not title:
            continue
        items.append(WebCandidate(title=title, url=url, domain=domain, snippet=snippet, label=label))

    # Fallback: split on blank lines when the block regex did not match.
    if not items:
        for block in body.split("\n\n"):
            m = re.match(r'\[\s*(\d+)\s*\]\s*Title:\s*(.+)', block.strip(), flags=re.IGNORECASE)
            if not m:
                continue
            try:
                label = int(m.group(1))
            except (ValueError, TypeError):
                continue
            title = m.group(2).strip()
            url_m = re.search(r'URL:\s*(\S+)', block, flags=re.IGNORECASE)
            dom_m = re.search(r'Domain:\s*(\S+)', block, flags=re.IGNORECASE)
            snip_m = re.search(r'Snippet:\s*(.*?)$', block, flags=re.IGNORECASE | re.DOTALL)
            items.append(WebCandidate(
                title=title,
                url=url_m.group(1).strip() if url_m else "",
                domain=dom_m.group(1).strip() if dom_m else "",
                snippet=snip_m.group(1).strip() if snip_m else "",
                label=label,
            ))

    items.sort(key=lambda c: c.label)
    return items


class EvidenceBuilder:
    """
    Builds evidence from chunks explicitly referenced by the LLM via [Chunk N] notation.

    Phase 2: Explicit citation parsing (replaces n-gram overlap Phase 1).
    Fallback: If no explicit references found, falls back to overlap matching.
    """

    def __init__(self, min_overlap: float = 0.15) -> None:
        self._min_overlap = min_overlap

    @traceable(name="evidence_builder", metadata={"stage": "evidence_builder"})
    def build(
        self,
        response_text: str,
        ranked_chunks: list[RankedChunk],
        source_policy: AnswerMode,
        answer_mode: str = "grounded",
        answer_mode_metadata: dict | None = None,
        web_candidates: list[WebCandidate] | None = None,
    ) -> EvidenceBuilderResult:
        meta = answer_mode_metadata or {}

        # Web-only answers carry policy=REASONING/NONE with no ranked chunks;
        # web candidates let them produce evidence/resources too.
        web_candidates = web_candidates or []
        has_candidates = bool(ranked_chunks) or bool(web_candidates)

        if source_policy.policy == SourcePolicy.NONE and not has_candidates:
            logger.info("stage=evidence_builder policy=none — no evidence")
            return EvidenceBuilderResult(
                evidence=[],
                source_policy=source_policy.policy,
                total_candidates=0,
                total_cited=0,
            )

        candidates: list = list(ranked_chunks)
        ranked_count = len(candidates)
        candidates.extend(web_candidates)
        total_candidates = len(candidates)

        # Phase 2: Parse explicit [Chunk N] references
        ref_indices = _parse_chunk_references(response_text)

        # Web-only answers: the model sees the tool's 1-based labels ([1] ..
        # [n]); a bare [N] reference resolves to web_candidates[N-1].
        if web_candidates and not ranked_chunks:
            for match in _WEB_BARE_REF_RE.finditer(response_text):
                n = int(match.group(1))
                if 1 <= n <= len(web_candidates):
                    ref_indices.append(n - 1)
            ref_indices = sorted(set(ref_indices))

        total_explicit = len(ref_indices)

        if ref_indices:
            logger.info(
                "stage=evidence_builder found %d explicit chunk references: %s",
                total_explicit, ref_indices,
            )
            cited_candidates: list[tuple[object, int]] = []
            seen: set[int] = set()
            for idx in ref_indices:
                if idx < len(candidates) and idx not in seen:
                    seen.add(idx)
                    cited_candidates.append((candidates[idx], idx))
            total_cited = len(cited_candidates)
        else:
            # Fallback: n-gram overlap matching
            logger.info("stage=evidence_builder no explicit references — falling back to n-gram overlap")
            cited_kb = self._find_cited_chunks_overlap(response_text, ranked_chunks)
            cited_web = self._find_cited_web_overlap(response_text, web_candidates, ranked_count)
            cited_candidates = cited_kb + cited_web
            total_cited = len(cited_candidates)

        method = RetrievalMethod(meta.get("retrieval_method", "hybrid")) \
            if meta.get("retrieval_method") in ("vector", "bm25", "hybrid") \
            else RetrievalMethod.hybrid
        if web_candidates and not ranked_chunks:
            method = RetrievalMethod.web

        evidence_items: list[EvidenceItem] = []
        seen_doc_ids: set[str] = set()

        confidence = meta.get("confidence", 0.0)
        confidence_label = confidence_from_score(confidence)

        for candidate, idx in cited_candidates:
            if isinstance(candidate, WebCandidate):
                doc_id = f"web-{candidate.url or candidate.title}"
                if doc_id in seen_doc_ids:
                    continue
                seen_doc_ids.add(doc_id)
                evidence_items.append(EvidenceItem(
                    id=doc_id,
                    title=candidate.title,
                    source_type="web",
                    url=candidate.url or None,
                    chunk=candidate.snippet[:300],
                    confidence_label=confidence_label,
                    retrieval_method=RetrievalMethod.web,
                    chunk_index=None,
                    total_chunks=total_cited,
                    document_id=candidate.domain or candidate.url or None,
                    page=None,
                    section=None,
                    citation_index=idx + 1,
                ))
                continue

            chunk = candidate.chunk
            doc_id = getattr(chunk, "chunk_id", None) or f"cited-{len(evidence_items)}"
            if doc_id in seen_doc_ids:
                continue
            seen_doc_ids.add(doc_id)

            src = getattr(chunk, "source", None) or getattr(chunk, "filename", None) or "unknown"

            # Prefer the document-stored chunk_index over positional reranked_rank
            doc_meta = chunk.document.metadata if hasattr(chunk, "document") else {}
            meta_chunk_index = doc_meta.get("chunk_index")
            if meta_chunk_index is not None:
                try:
                    meta_chunk_index = int(meta_chunk_index)
                except (ValueError, TypeError):
                    meta_chunk_index = None

            # Page and section from chunk metadata (populated during ingestion for PDFs)
            page = chunk.page if hasattr(chunk, "page") else doc_meta.get("page")
            if page is not None:
                try:
                    page = int(page)
                except (ValueError, TypeError):
                    page = None

            section = (
                chunk.chapter
                if hasattr(chunk, "chapter")
                else doc_meta.get("chapter") or doc_meta.get("section")
            )
            if section is not None:
                section = str(section)

            evidence_items.append(EvidenceItem(
                id=doc_id,
                title=src,
                source_type="knowledge",
                chunk=chunk.document.page_content[:300] if hasattr(chunk, "document") else "",
                confidence_label=confidence_label,
                retrieval_method=method,
                chunk_index=meta_chunk_index if meta_chunk_index is not None else (
                    idx if idx < ranked_count else None
                ),
                total_chunks=total_cited,
                document_id=src,
                page=page,
                section=section,
                citation_index=idx + 1,
                raw_score=chunk.score if hasattr(chunk, "score") else None,
                reranker_score=getattr(candidate, "reranker_score", None),
            ))

        logger.info(
            "stage=evidence_builder policy=%s candidates=%d explicit=%d cited=%d evidence=%d",
            source_policy.policy.value,
            total_candidates,
            total_explicit,
            total_cited,
            len(evidence_items),
        )

        return EvidenceBuilderResult(
            evidence=evidence_items,
            source_policy=source_policy.policy,
            total_candidates=total_candidates,
            total_cited=total_cited,
        )

    # ── Fallback: n-gram overlap ──────────────────────────────────────────────

    def _extract_ngrams(self, text: str, n: int = 5) -> set[str]:
        cleaned = re.sub(r'\s+', ' ', text.lower().strip())
        if len(cleaned) < n:
            return {cleaned}
        return {cleaned[i:i+n] for i in range(len(cleaned) - n + 1)}

    def _compute_overlap(self, response_text: str, chunk_text: str, threshold: float = 0.15) -> float:
        response_ngrams = self._extract_ngrams(response_text)
        chunk_ngrams = self._extract_ngrams(chunk_text)
        if not chunk_ngrams:
            return 0.0
        intersection = response_ngrams & chunk_ngrams
        return len(intersection) / len(chunk_ngrams)

    def _find_cited_chunks_overlap(
        self,
        response_text: str,
        ranked_chunks: list[RankedChunk],
    ) -> list[tuple[RankedChunk, int]]:
        """Return (RankedChunk, position) pairs whose content overlaps the response."""
        cited: list[tuple[RankedChunk, int]] = []
        for position, rc in enumerate(ranked_chunks):
            # Skip chunks with negative reranker scores (FlashRank scores < 0 mean cross-encoder evaluated chunk as irrelevant)
            score = getattr(rc, "reranker_score", None)
            if score is not None and score < 0.0:
                logger.info(
                    "skipping_irrelevant_evidence_chunk score=%.4f source=%s",
                    score, getattr(rc.chunk, "source", "unknown"),
                )
                continue
            chunk_text = rc.chunk.document.page_content
            overlap = self._compute_overlap(response_text, chunk_text, self._min_overlap)
            if overlap >= self._min_overlap:
                cited.append((rc, position))
        return cited

    def _find_cited_web_overlap(
        self,
        response_text: str,
        web_candidates: list[WebCandidate],
        ranked_count: int,
    ) -> list[tuple[WebCandidate, int]]:
        """Match response text against web titles/snippets (fallback path)."""
        cited: list[tuple[WebCandidate, int]] = []
        for position, wc in enumerate(web_candidates):
            candidate_text = f"{wc.title}\n{wc.snippet}"
            overlap = self._compute_overlap(response_text, candidate_text, self._min_overlap)
            if overlap >= self._min_overlap:
                cited.append((wc, ranked_count + position))
        return cited