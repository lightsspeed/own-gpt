from pydantic import BaseModel
from typing import Optional, Any
from enum import Enum
from datetime import datetime


class ConfidenceLabel(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"
    no_evidence = "no_evidence"


class RetrievalMethod(str, Enum):
    vector = "vector"
    bm25 = "bm25"
    hybrid = "hybrid"
    web = "web"
    memory = "memory"
    none_method = "none"


class EvidenceItem(BaseModel):
    """A single piece of evidence attached to an AI response."""

    id: str
    title: str
    source_type: str  # "knowledge" | "web" | "memory" | "file"
    url: Optional[str] = None
    chunk: Optional[str] = None
    confidence_label: ConfidenceLabel = ConfidenceLabel.medium
    retrieval_method: RetrievalMethod = RetrievalMethod.hybrid
    chunk_index: Optional[int] = None     # actual document chunk_index from metadata
    total_chunks: Optional[int] = None
    document_id: Optional[str] = None    # filename / stable document reference
    page: Optional[int] = None           # PDF page number (1-based), when available
    section: Optional[str] = None        # Chapter / heading when available
    citation_index: Optional[int] = None # canonical 1-based citation index (the single
                                         # authoritative numbering used across UI pill,
                                         # hover card, resource list, and PDF export;
                                         # maps [Chunk N]→N+1 and [N]→N)
    metadata: dict[str, Any] = {}

    # Internal / developer-only fields (not serialized for public)
    raw_score: Optional[float] = None
    reranker_score: Optional[float] = None
    retrieval_latency_ms: Optional[float] = None
    embedding_model: Optional[str] = None


class EvidenceBundle(BaseModel):
    """Collection of evidence items for a single assistant response."""

    items: list[EvidenceItem] = []
    answer_mode: str = "grounded"


def confidence_from_score(score: float | None) -> ConfidenceLabel:
    if score is None:
        return ConfidenceLabel.medium
    if score >= 0.85:
        return ConfidenceLabel.high
    if score >= 0.60:
        return ConfidenceLabel.medium
    return ConfidenceLabel.low
