from __future__ import annotations

import dataclasses
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from app.agent.pipeline.retriever import RetrievedChunk
from app.agent.pipeline.reranker import RankedChunk
from app.agent.pipeline.tracing import PipelineTrace

if TYPE_CHECKING:
    from app.agent.pipeline.pipeline import PipelineContext
    from app.agent.pipeline.confidence import ConfidenceResult


def _build_chunk_eval(chunk: RetrievedChunk, rank: Optional[int] = None) -> ChunkEvaluation:
    return ChunkEvaluation(
        chunk_id=chunk.chunk_id,
        content=chunk.document.page_content,
        source=chunk.source,
        page=chunk.page,
        chapter=chunk.chapter,
        score=chunk.score,
        provenance=Provenance(**{k: v for k, v in chunk.provenance.items() if v is not None}) if chunk.provenance else None,
    )


def _build_ranked_chunk_eval(rc: RankedChunk) -> ChunkEvaluation:
    return ChunkEvaluation(
        chunk_id=rc.chunk.chunk_id,
        content=rc.chunk.document.page_content,
        source=rc.chunk.source,
        page=rc.chunk.page,
        chapter=rc.chunk.chapter,
        score=rc.chunk.score,
        provenance=Provenance(**{k: v for k, v in rc.chunk.provenance.items() if v is not None}) if rc.chunk.provenance else None,
    )


def build_evaluation_result(
    ctx: PipelineContext,
    answer: str = "",
    latencies: Optional[dict] = None,
) -> EvaluationResult:
    trace = ctx.trace
    result = EvaluationResult(
        query=ctx.question,
        answer=answer,
        session_id=ctx.session_id,
        retrieved_chunks=[_build_chunk_eval(c) for c in ctx.retrieved_chunks],
        reranked_chunks=[_build_ranked_chunk_eval(rc) for rc in ctx.ranked_chunks],
        context=ctx.context_text or "",
        trace=dataclasses.asdict(trace) if trace else {},
        latencies={
            **(latencies or {}),
            **(trace.extra.get("timing_breakdown", {}) if trace else {}),
            "total_ms": trace.total_latency_ms if trace else 0.0,
        },
        confidence=ctx.confidence.overall if ctx.confidence else 0.0,
        confidence_decision=ctx.confidence.decision if ctx.confidence else "",
    )
    return result


@dataclass
class Provenance:
    retrieval_method: str = "vector"  # "vector" | "bm25" | "both"
    vector_score: Optional[float] = None
    vector_rank: Optional[int] = None
    bm25_score: Optional[float] = None
    bm25_rank: Optional[int] = None
    rrf_score: Optional[float] = None
    rrf_rank: Optional[int] = None
    reranker_score: Optional[float] = None
    reranker_rank: Optional[int] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class ChunkEvaluation:
    chunk_id: str
    content: str
    source: str
    page: Optional[int] = None
    chapter: Optional[str] = None
    score: float = 0.0
    provenance: Optional[Provenance] = None

    def to_dict(self) -> dict:
        d = {
            "chunk_id": self.chunk_id,
            "content": self.content[:500],
            "source": self.source,
            "score": self.score,
        }
        if self.page is not None:
            d["page"] = self.page
        if self.chapter is not None:
            d["chapter"] = self.chapter
        if self.provenance is not None:
            d["provenance"] = self.provenance.to_dict()
        return d


@dataclass
class EvaluationResult:
    query: str
    answer: str = ""
    session_id: str = ""

    retrieved_chunks: List[ChunkEvaluation] = field(default_factory=list)
    reranked_chunks: List[ChunkEvaluation] = field(default_factory=list)
    context: str = ""
    prompt: str = ""

    trace: Dict[str, Any] = field(default_factory=dict)
    latencies: Dict[str, float] = field(default_factory=dict)

    confidence: float = 0.0
    confidence_decision: str = ""

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "answer": self.answer,
            "session_id": self.session_id,
            "retrieved_chunks": [c.to_dict() for c in self.retrieved_chunks],
            "reranked_chunks": [c.to_dict() for c in self.reranked_chunks],
            "context": self.context,
            "trace": self.trace,
            "latencies": self.latencies,
            "confidence": self.confidence,
            "confidence_decision": self.confidence_decision,
        }
