"""
Tests for inline-citation web evidence: tool-output parsing and web EvidenceItems.

Covers:
1. parse_web_results on the exact web_search_impl output format (+ fallback).
2. Web-only answers: bare [N] references resolve to 1-based tool labels.
3. Web-only answers: [Chunk N] references resolve against the 0-based candidate list.
4. Mixed KB + web candidate lists keep [Chunk N] numbering stable.
5. SourcePolicy.NONE produces evidence only when web candidates exist.
6. citation_index is populated and stable for both KB and web items.
7. Overlap fallback for web when no explicit references are present.
"""

from unittest.mock import MagicMock

from langchain_core.documents import Document

from app.models.evidence import ConfidenceLabel  # noqa: F401
from app.agent.pipeline.evidence_builder import (
    EvidenceBuilder,
    WebCandidate,
    parse_web_results,
)
from app.agent.pipeline.reranker import RankedChunk
from app.agent.pipeline.retriever import RetrievedChunk
from app.agent.pipeline.source_policy import AnswerMode, SourcePolicy

TOOL_OUTPUT = (
    "Web Search Results for 'testing frameworks':\n\n"
    "[1] Title: Pytest Documentation\n"
    "    URL: https://docs.pytest.org/\n"
    "    Domain: docs.pytest.org\n"
    "    Snippet: pytest is a mature full-featured Python testing tool.\n\n"
    "[2] Title: Vitest Guide\n"
    "    URL: https://vitest.dev/guide/\n"
    "    Domain: vitest.dev\n"
    "    Snippet: Vitest is a blazing fast unit test framework powered by Vite.\n\n"
    "[3] Title: Unittest (Python)\n"
    "    URL: https://docs.python.org/3/library/unittest.html\n"
    "    Domain: docs.python.org\n"
    "    Snippet: unittest is the standard unit testing library of Python."
)


def _parsed() -> list[WebCandidate]:
    return parse_web_results(TOOL_OUTPUT)


def _web_policy() -> AnswerMode:
    return AnswerMode.from_policy(SourcePolicy.NONE, reason="web search")


def _kb_policy() -> AnswerMode:
    return AnswerMode.from_policy(SourcePolicy.KB, reason="kb")


def _ranked(texts: list[str]) -> list[RankedChunk]:
    chunks = []
    for i, text in enumerate(texts):
        doc = Document(
            page_content=text,
            metadata={"filename": f"doc-{i}.pdf", "chunk_index": i * 2, "page": i + 1},
        )
        rc = RetrievedChunk(
            document=doc,
            score=0.9 - i * 0.1,
            source=f"doc-{i}.pdf",
            collection="own_gpt_docs",
        )
        chunks.append(RankedChunk(chunk=rc, reranker_score=4.0 - i, original_rank=i, reranked_rank=i))
    return chunks


# ── parse_web_results ──────────────────────────────────────────────────────


def test_parse_web_results_parses_tool_format():
    items = _parsed()
    assert len(items) == 3
    assert items[0].label == 1
    assert items[0].title == "Pytest Documentation"
    assert items[0].url == "https://docs.pytest.org/"
    assert items[0].domain == "docs.pytest.org"
    assert "mature full-featured Python testing tool" in items[0].snippet
    assert items[2].label == 3
    assert items[2].title == "Unittest (Python)"


def test_parse_web_results_returns_display_order():
    items = _parsed()
    assert [i.title for i in items] == [
        "Pytest Documentation",
        "Vitest Guide",
        "Unittest (Python)",
    ]


def test_parse_web_results_blank_line_fallback():
    text = (
        "Web Search Results for 'x':\n\n"
        "[1] Title: Only Title Item\n"
        "    URL: https://example.com\n"
        "    Snippet: some snippet\n\n"
        "[2] Title: Second Item\n"
        "    URL: https://example.org\n"
    )
    # Break block structure with double newlines inside the snippet field.
    broken = text.replace("some snippet", "some\n\nsnippet")
    items = parse_web_results(broken)
    assert len(items) == 2
    assert items[0].title == "Only Title Item"
    assert items[1].title == "Second Item"


def test_parse_web_results_never_raises():
    assert parse_web_results("") == []
    assert parse_web_results(None) == []
    assert parse_web_results("No structured results here.") == []
    assert parse_web_results("Web search encountered an error: timeout") == []


# ── Web-only evidence ───────────────────────────────────────────────────────


def test_web_only_bare_reference_resolves_tool_labels():
    builder = EvidenceBuilder()
    result = builder.build(
        response_text="Pytest is a mature testing tool [1], while Vitest is powered by Vite [2].",
        ranked_chunks=[],
        source_policy=_web_policy(),
        web_candidates=_parsed(),
    )
    assert len(result.evidence) == 2
    assert result.evidence[0].source_type == "web"
    assert result.evidence[0].title == "Pytest Documentation"
    assert result.evidence[0].url == "https://docs.pytest.org/"
    assert result.evidence[0].citation_index == 1
    assert result.evidence[1].title == "Vitest Guide"
    assert result.evidence[1].citation_index == 2
    assert result.evidence[1].chunk_index is None
    assert result.evidence[1].retrieval_method.value == "web"


def test_web_only_bare_reference_maps_to_1based_canonical_index():
    builder = EvidenceBuilder()
    result = builder.build(
        response_text="According to pytest docs [1].",
        ranked_chunks=[],
        source_policy=_web_policy(),
        web_candidates=_parsed(),
    )
    # Bare [N] mirrors the tool's 1-based label → canonical citation_index = N.
    assert len(result.evidence) == 1
    assert result.evidence[0].citation_index == 1
    assert result.evidence[0].title == "Pytest Documentation"


def test_web_only_chunk_reference_resolves_candidate_list():
    builder = EvidenceBuilder()
    result = builder.build(
        response_text="[Chunk 2] references the third listed result.",
        ranked_chunks=[],
        source_policy=_web_policy(),
        web_candidates=_parsed(),
    )
    assert len(result.evidence) == 1
    assert result.evidence[0].title == "Unittest (Python)"
    assert result.evidence[0].citation_index == 3


def test_none_policy_empty_without_candidates():
    builder = EvidenceBuilder()
    result = builder.build(
        response_text="Nothing to cite.",
        ranked_chunks=[],
        source_policy=_web_policy(),
        web_candidates=[],
    )
    assert result.evidence == []
    assert result.total_candidates == 0


def test_none_policy_with_web_candidates_produces_evidence():
    builder = EvidenceBuilder()
    result = builder.build(
        response_text="According to the web, pytest is mature [1].",
        ranked_chunks=[],
        source_policy=_web_policy(),
        web_candidates=_parsed(),
    )
    assert len(result.evidence) == 1
    assert result.evidence[0].source_type == "web"
    assert result.evidence[0].chunk == _parsed()[0].snippet[:300]


# ── Mixed KB + web ──────────────────────────────────────────────────────────


def test_mixed_kb_and_web_numbering_no_drift():
    kb = _ranked([
        "Alpha is the first grounded claim.",
        "Beta is the second grounded claim.",
        "Gamma is the third grounded claim.",
    ])
    builder = EvidenceBuilder()
    result = builder.build(
        response_text="Alpha holds [Chunk 0], Beta follows [Chunk 1], and web says [Chunk 3].",
        ranked_chunks=kb,
        source_policy=_kb_policy(),
        web_candidates=_parsed(),
        answer_mode_metadata={"confidence": 0.9, "retrieval_method": "hybrid"},
    )
    assert len(result.evidence) == 3
    kb_items = [e for e in result.evidence if e.source_type == "knowledge"]
    web_items = [e for e in result.evidence if e.source_type == "web"]
    # [Chunk N] → canonical citation_index = N + 1 (1-based)
    assert [e.citation_index for e in kb_items] == [1, 2]
    assert [e.title for e in kb_items] == ["doc-0.pdf", "doc-1.pdf"]
    assert len(web_items) == 1
    assert web_items[0].title == "Pytest Documentation"
    assert web_items[0].citation_index == 4
    assert kb_items[0].chunk_index == 0  # metadata chunk_index (i*2 = 0)


def test_mixed_kb_index_with_metadata_chunk_index():
    kb = _ranked(["Only one document chunk here."])
    builder = EvidenceBuilder()
    result = builder.build(
        response_text="The document claims it [Chunk 0].",
        ranked_chunks=kb,
        source_policy=_kb_policy(),
        web_candidates=None,
        answer_mode_metadata={"confidence": 0.9},
    )
    assert len(result.evidence) == 1
    # metadata chunk_index is authoritative (i*2 = 0 here)
    assert result.evidence[0].chunk_index == 0
    assert result.evidence[0].citation_index == 1


# ── Fallback overlap ────────────────────────────────────────────────────────


def test_web_overlap_fallback_without_explicit_refs():
    builder = EvidenceBuilder()
    result = builder.build(
        response_text="mature full-featured Python testing tool documentation",
        ranked_chunks=[],
        source_policy=_web_policy(),
        web_candidates=_parsed(),
    )
    assert len(result.evidence) == 1
    assert result.evidence[0].title == "Pytest Documentation"