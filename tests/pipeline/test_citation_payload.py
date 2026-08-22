"""
Unit tests for V3 Phase 5: Citation Transparency & Document Inspector.

Tests:
1. EvidenceItem model serialization & new page/section fields.
2. EvidenceBuilder.build() populates page, section, and document chunk_index.
"""

import pytest
from unittest.mock import MagicMock
from langchain_core.documents import Document

from app.models.evidence import EvidenceItem, ConfidenceLabel, RetrievalMethod
from app.agent.pipeline.evidence_builder import EvidenceBuilder
from app.agent.pipeline.reranker import RankedChunk
from app.agent.pipeline.retriever import RetrievedChunk
from app.agent.pipeline.source_policy import SourcePolicy, AnswerMode


def test_evidence_item_model_fields():
    """Verify EvidenceItem correctly holds and serializes page and section fields."""
    item = EvidenceItem(
        id="chunk-101",
        title="report.pdf",
        source_type="knowledge",
        chunk="Sample text excerpt",
        confidence_label=ConfidenceLabel.high,
        retrieval_method=RetrievalMethod.hybrid,
        chunk_index=3,
        total_chunks=12,
        document_id="report.pdf",
        page=4,
        section="Executive Summary",
    )

    data = item.model_dump()
    assert data["page"] == 4
    assert data["section"] == "Executive Summary"
    assert data["chunk_index"] == 3
    assert data["document_id"] == "report.pdf"


def test_evidence_builder_populates_page_section_chunk_index():
    """Verify EvidenceBuilder extracts page, section, and metadata chunk_index from RetrievedChunk."""
    doc = Document(
        page_content="This is the ground truth claim [Chunk 0].",
        metadata={
            "filename": "sample.pdf",
            "chunk_index": 7,
            "page": 12,
            "chapter": "Chapter 3: Methodology",
        },
    )
    rc_obj = RetrievedChunk(
        document=doc,
        score=0.92,
        source="sample.pdf",
        collection="own_gpt_docs",
    )
    ranked_chunk = RankedChunk(
        chunk=rc_obj,
        reranker_score=4.5,
        original_rank=0,
        reranked_rank=0,
    )

    builder = EvidenceBuilder()
    policy = AnswerMode(
        policy=SourcePolicy.KB,
        contract=MagicMock(system_directive="test"),
    )

    result = builder.build(
        response_text="The report states something [Chunk 0].",
        ranked_chunks=[ranked_chunk],
        source_policy=policy,
        answer_mode="grounded",
        answer_mode_metadata={"confidence": 0.95, "retrieval_method": "hybrid"},
    )

    assert len(result.evidence) == 1
    ev = result.evidence[0]
    assert ev.title == "sample.pdf"
    assert ev.chunk_index == 7  # from metadata, not reranked_rank 0
    assert ev.page == 12
    assert ev.section == "Chapter 3: Methodology"
