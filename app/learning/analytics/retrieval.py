"""
RetrievalIntelligence + ChunkIntelligence — analyzes document and chunk effectiveness.

Per-document metrics:
  - Retrieved count, reranked count, cited count
  - Average confidence, thumb rate, acceptance rate

Per-chunk quality scoring:
  - Excellent / Good / Weak / Dead classification
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

from ..storage.sqlite import LearningStore

logger = logging.getLogger(__name__)


@dataclass
class RetrievalIntelligenceReport:
    per_document: list[dict] = field(default_factory=list)
    per_chunk: list[dict] = field(default_factory=list)
    chunk_quality: dict = field(default_factory=dict)
    top_documents: list[dict] = field(default_factory=list)
    weakest_documents: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "per_document": self.per_document,
            "per_chunk": self.per_chunk[:50],
            "chunk_quality": self.chunk_quality,
            "top_documents": self.top_documents[:10],
            "weakest_documents": self.weakest_documents[:10],
        }


class RetrievalIntelligence:
    def __init__(self, store: LearningStore):
        self._store = store

    def analyze(self) -> RetrievalIntelligenceReport:
        per_doc = self._per_document()
        per_chunk = self._per_chunk()
        quality = self._classify_chunks(per_chunk)
        top = sorted(per_doc, key=lambda d: d.get("avg_confidence", 0) * d.get("reranked_count", 0), reverse=True) if per_doc else []
        weak = sorted(per_doc, key=lambda d: d.get("accept_rate", 1)) if per_doc else []
        return RetrievalIntelligenceReport(
            per_document=per_doc,
            per_chunk=per_chunk,
            chunk_quality=quality,
            top_documents=top[:10],
            weakest_documents=weak[:10],
        )

    def _per_document(self) -> list[dict]:
        """Parse `documents` JSON field and aggregate per-document stats."""
        rows = self._store.query_sql("""
            SELECT documents, confidence, accepted, record_id FROM learning_records
            WHERE documents IS NOT NULL AND documents != '' AND documents != '[]'
        """)
        doc_stats: dict[str, dict] = {}
        for r in rows:
            try:
                docs = json.loads(r["documents"]) if isinstance(r["documents"], str) else r.get("documents", [])
            except (json.JSONDecodeError, TypeError):
                continue
            if not docs:
                continue
            confidence = r.get("confidence", 0) or 0
            accepted = bool(r.get("accepted", 1))
            for doc in docs:
                if doc not in doc_stats:
                    doc_stats[doc] = {"retrieved": 0, "confidence_sum": 0.0, "accepted_count": 0, "record_ids": []}
                doc_stats[doc]["retrieved"] += 1
                doc_stats[doc]["confidence_sum"] += confidence
                if accepted:
                    doc_stats[doc]["accepted_count"] += 1
                doc_stats[doc]["record_ids"].append(r["record_id"])

        result = []
        for doc, stats in sorted(doc_stats.items(), key=lambda x: -x[1]["retrieved"]):
            result.append({
                "document": doc,
                "retrieved_count": stats["retrieved"],
                "avg_confidence": round(stats["confidence_sum"] / stats["retrieved"], 3) if stats["retrieved"] else 0,
                "accept_rate": round(stats["accepted_count"] / stats["retrieved"], 3) if stats["retrieved"] else 0,
            })
        return result

    def _per_chunk(self) -> list[dict]:
        """Parse `chunks` JSON field and aggregate per-chunk stats."""
        rows = self._store.query_sql("""
            SELECT chunks, confidence, accepted, record_id FROM learning_records
            WHERE chunks IS NOT NULL AND chunks != '' AND chunks != '[]'
        """)
        chunk_stats: dict[str, dict] = {}
        for r in rows:
            try:
                chunks = json.loads(r["chunks"]) if isinstance(r["chunks"], str) else r.get("chunks", [])
            except (json.JSONDecodeError, TypeError):
                continue
            if not chunks:
                continue
            confidence = r.get("confidence", 0) or 0
            accepted = bool(r.get("accepted", 1))
            for c in chunks:
                cid = c.get("chunk_id", c.get("source", "unknown"))
                if cid not in chunk_stats:
                    chunk_stats[cid] = {"retrieved": 0, "confidence_sum": 0.0, "accepted_count": 0, "source": c.get("source", ""), "page": c.get("page")}
                chunk_stats[cid]["retrieved"] += 1
                chunk_stats[cid]["confidence_sum"] += confidence
                if accepted:
                    chunk_stats[cid]["accepted_count"] += 1

        result = []
        for cid, stats in sorted(chunk_stats.items(), key=lambda x: -x[1]["retrieved"]):
            result.append({
                "chunk_id": cid,
                "source": stats["source"],
                "page": stats["page"],
                "retrieved_count": stats["retrieved"],
                "avg_confidence": round(stats["confidence_sum"] / stats["retrieved"], 3) if stats["retrieved"] else 0,
                "accept_rate": round(stats["accepted_count"] / stats["retrieved"], 3) if stats["retrieved"] else 0,
            })
        return result

    def _classify_chunks(self, chunks: list[dict]) -> dict[str, list[str]]:
        """Classify chunks into quality tiers based on usage patterns."""
        excellent, good, weak, dead = [], [], [], []
        for c in chunks:
            retrieved = c["retrieved_count"]
            accept = c["accept_rate"]
            if retrieved >= 10 and accept >= 0.90:
                excellent.append(c["chunk_id"])
            elif retrieved >= 5 and accept >= 0.70:
                good.append(c["chunk_id"])
            elif retrieved >= 3 and accept < 0.40:
                weak.append(c["chunk_id"])
            elif retrieved >= 5 and accept < 0.20:
                dead.append(c["chunk_id"])
        return {
            "excellent": len(excellent),
            "good": len(good),
            "weak": len(weak),
            "dead": len(dead),
        }
