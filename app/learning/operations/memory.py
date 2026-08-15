"""Structured semantic memory — immutable, scoped, lineage-preserving facts.

Every memory write produces an immutable MemoryFact artifact stored as an
append-only JSON file, mirroring the ToolExecution pattern:

  - scope:  "global"            → facts available to every conversation
            "session:<id>"      → facts scoped to one conversation
  - dedupe: saving the exact same fact in the same scope returns the existing
            artifact (idempotent) — memory is never duplicated
  - lifecycle: forgetting a fact appends a superseded event and flips status;
            history is never rewritten (the old artifact keeps its content)

Lineage: a superseded fact retains its id/timestamp; the supersession event is
the link to the operator decision that retired it.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional, Sequence

logger = logging.getLogger(__name__)

MEMORY_DIR = "memory_facts"

SCOPE_GLOBAL = "global"
SCOPE_PREFIX_SESSION = "session:"

STATUS_ACTIVE = "active"
STATUS_SUPERSEDED = "superseded"

SOURCE_TOOL_CALL = "tool_call"
SOURCE_OPERATOR = "operator"
SOURCE_CONSOLIDATION = "consolidation"


def session_scope(session_id: str) -> str:
    """Scope key for facts tied to one conversation."""
    return f"{SCOPE_PREFIX_SESSION}{session_id}"


def is_session_scope(scope: str) -> bool:
    return scope.startswith(SCOPE_PREFIX_SESSION)


@dataclass
class MemoryEvent:
    status: str
    at: str = ""
    note: str = ""

    def __post_init__(self):
        if not self.at:
            self.at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {"status": self.status, "at": self.at, "note": self.note}


@dataclass
class MemoryFact:
    """Immutable semantic memory artifact."""
    id: str = ""
    fact: str = ""
    scope: str = SCOPE_GLOBAL
    source: str = SOURCE_TOOL_CALL
    created_at: str = ""
    status: str = STATUS_ACTIVE     # active | superseded
    version: int = 1
    seq: int = 0                    # monotonic creation order (persisted)
    supersedes: list[str] = field(default_factory=list)  # parent fact ids (lineage)
    events: list[MemoryEvent] = field(default_factory=list)

    def __post_init__(self):
        if not self.id:
            self.id = f"mem-{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def append_event(self, status: str, note: str = ""):
        self.events.append(MemoryEvent(status=status, note=note))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "fact": self.fact,
            "scope": self.scope,
            "source": self.source,
            "created_at": self.created_at,
            "status": self.status,
            "version": self.version,
            "seq": self.seq,
            "supersedes": list(self.supersedes),
            "events": [e.to_dict() for e in self.events],
        }

    @staticmethod
    def from_dict(data: dict) -> "MemoryFact":
        events = [MemoryEvent(**e) for e in data.get("events", [])]
        kwargs = {k: v for k, v in data.items() if k != "events"}
        return MemoryFact(events=events, **kwargs)


class MemoryStore:
    """Persists MemoryFact artifacts (append-only per id)."""

    def __init__(self, store_dir: str = MEMORY_DIR):
        self._store_dir = store_dir
        self._seq = 0
        self._seq_loaded = False
        os.makedirs(store_dir, exist_ok=True)

    # ── Writes ──────────────────────────────────────────────────────────────

    def store_fact(
        self,
        fact: str,
        scope: str = SCOPE_GLOBAL,
        source: str = SOURCE_TOOL_CALL,
        note: str = "",
    ) -> MemoryFact:
        """Persist a fact. Idempotent for an identical active fact in scope.

        Returns the existing artifact when the same normalized fact is already
        active in the same scope; otherwise creates and persists a new artifact.
        """
        normalized = self._normalize(fact)
        if not normalized:
            raise ValueError("fact must not be empty")

        existing = self._find_active_by_text(normalized, scope)
        if existing is not None:
            return existing

        record = MemoryFact(
            fact=normalized,
            scope=scope,
            source=source,
            seq=self._next_seq(),
        )
        record.append_event("stored", note=note or f"stored via {source}")
        return self.save(record)

    def forget(self, fact_id: str, operator: str = "operator", note: str = "") -> Optional[MemoryFact]:
        """Supersede an active fact (append-only). Nothing in history is rewritten."""
        fact = self.get(fact_id)
        if not fact:
            return None
        if fact.status != STATUS_ACTIVE:
            return fact
        fact.append_event(
            STATUS_SUPERSEDED,
            note=note or f"forgotten by {operator}",
        )
        fact.status = STATUS_SUPERSEDED
        return self.save(fact)

    def save(self, fact: MemoryFact) -> MemoryFact:
        path = self._path(fact.id)
        with open(path, "w") as f:
            json.dump(fact.to_dict(), f, indent=2, default=str)
        return fact

    # ── Reads ───────────────────────────────────────────────────────────────

    def get(self, fact_id: str) -> Optional[MemoryFact]:
        path = self._path(fact_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r") as f:
                return MemoryFact.from_dict(json.load(f))
        except (json.JSONDecodeError, IOError, TypeError):
            logger.warning("memory_fact_read_failed id=%s", fact_id)
            return None

    def list_active(self, scope: Optional[str] = None) -> list[MemoryFact]:
        """Active facts, newest first. scope=None returns all active scopes."""
        return self._scan(status=STATUS_ACTIVE, scope=scope)

    def list_superseded(self, scope: Optional[str] = None) -> list[MemoryFact]:
        return self._scan(status=STATUS_SUPERSEDED, scope=scope)

    def list_all(self, scope: Optional[str] = None, limit: int = 100) -> list[MemoryFact]:
        return self._scan(status=None, scope=scope, limit=limit)

    def active_count(self) -> int:
        return len(self.list_active())

    def find_active_fact(self, fact_text: str, scope: str = SCOPE_GLOBAL) -> Optional[MemoryFact]:
        """Find the active fact whose normalized text matches, within a scope."""
        return self._find_active_by_text(self._normalize(fact_text), scope)

    # ── Internals ───────────────────────────────────────────────────────────

    def _find_active_by_text(self, normalized: str, scope: str) -> Optional[MemoryFact]:
        for fact in self.list_active(scope=scope):
            if self._normalize(fact.fact) == normalized:
                return fact
        return None

    def _scan(self, status: Optional[str], scope: Optional[str], limit: int = 200) -> list[MemoryFact]:
        result = []
        for path in self._iter_fact_files():
            try:
                with open(path, "r") as f:
                    fact = MemoryFact.from_dict(json.load(f))
            except (json.JSONDecodeError, IOError, TypeError):
                continue
            if status and fact.status != status:
                continue
            if scope:
                # "session" matches any session-scoped fact (prefix); other values match exactly.
                if scope == "session" and not is_session_scope(fact.scope):
                    continue
                if scope != "session" and fact.scope != scope:
                    continue
            result.append(fact)
        result.sort(key=lambda x: x.seq, reverse=True)
        return result[:limit]

    def _next_seq(self) -> int:
        """Monotonic sequence across process restarts (persisted in files)."""
        if not self._seq_loaded:
            max_seq = 0
            for path in self._iter_fact_files():
                try:
                    with open(path, "r") as f:
                        data = json.load(f)
                    max_seq = max(max_seq, int(data.get("seq", 0)))
                except (json.JSONDecodeError, IOError, TypeError, ValueError):
                    continue
            self._seq = max_seq
            self._seq_loaded = True
        self._seq += 1
        return self._seq

    def _path(self, fact_id: str) -> str:
        return os.path.join(self._store_dir, f"{fact_id}.json")

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(str(text).strip().lower().split())

    def _iter_fact_files(self):
        """Yield JSON paths, skipping dotfiles (e.g. the embedding index)."""
        if not os.path.exists(self._store_dir):
            return
        for fname in os.listdir(self._store_dir):
            if fname.startswith(".") or not fname.endswith(".json"):
                continue
            yield os.path.join(self._store_dir, fname)


class MemoryEmbeddingIndex:
    """Derived embedding sidecar for memory facts.

    Not an artifact — a rebuildable projection (fact_id -> vector) that powers
    query-relevant memory recall. Embeddings are computed lazily for facts
    missing from the index and persisted next to the fact files.
    """

    INDEX_FILE = ".memory_index.json"

    def __init__(
        self,
        store_dir: str = MEMORY_DIR,
        embed_fn: Optional[Callable[[list[str]], list[list[float]]]] = None,
        index_file: str = INDEX_FILE,
    ):
        self._store_dir = store_dir
        self._embed_fn = embed_fn or self._default_embed_many
        self._index_file = index_file
        self._index: dict[str, list[float]] = self._load()
        os.makedirs(store_dir, exist_ok=True)

    # ── Embedding providers ─────────────────────────────────────────────────

    @staticmethod
    def _default_embed_many(texts: list[str]) -> list[list[float]]:
        from langchain_openai import OpenAIEmbeddings
        from app.core.config import settings

        if not hasattr(MemoryEmbeddingIndex, "_model"):
            MemoryEmbeddingIndex._model = OpenAIEmbeddings(api_key=settings.OPENAI_API_KEY)
        return MemoryEmbeddingIndex._model.embed_documents(texts)

    # ── Index management ────────────────────────────────────────────────────

    def ensure_embeddings(self, facts: Sequence[MemoryFact]) -> None:
        """Compute and persist embeddings for facts missing from the index."""
        missing = [f for f in facts if f.id not in self._index]
        if not missing:
            return
        try:
            vectors = self._embed_fn([f.fact for f in missing])
        except Exception:
            return  # index stays incomplete; caller degrades gracefully
        for fact, vector in zip(missing, vectors):
            self._index[fact.id] = list(vector)
        self._persist()

    def drop(self, fact_id: str) -> None:
        if fact_id in self._index:
            del self._index[fact_id]
            self._persist()

    def rebuild(self) -> int:
        """Recompute embeddings for ALL active facts (e.g. embedder change)."""
        active = MemoryStore(self._store_dir).list_active()
        self._index = {}
        self.ensure_embeddings(active)
        return len(active)

    # ── Retrieval ───────────────────────────────────────────────────────────

    def select_for_query(
        self,
        query: str,
        facts: Sequence[MemoryFact],
        k: int = 5,
        min_score: float = 0.0,
    ) -> list[MemoryFact]:
        """Top-k facts most similar to the query (cosine), above a score floor.

        Returns all when the list is small. Facts without embeddings are
        skipped. Results preserve descending similarity; ties keep creation
        order. A min_score below 0 means "no floor".
        """
        if not query.strip() or not facts:
            return list(facts)
        self.ensure_embeddings(facts)
        try:
            query_vector = self._embed_fn([query])[0]
        except Exception:
            return list(facts)[:k]
        similarities = []
        for fact in facts:
            vector = self._index.get(fact.id)
            if vector is None:
                continue
            score = cosine_similarity(query_vector, vector)
            if score < min_score:
                continue
            similarities.append((score, fact.seq, fact))
        similarities.sort(key=lambda x: (-x[0], x[1]))
        return [fact for _, _, fact in similarities[:k]]

    # ── Internals ───────────────────────────────────────────────────────────

    def _load(self) -> dict[str, list[float]]:
        path = os.path.join(self._store_dir, self._index_file)
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r") as f:
                data = json.load(f)
            return {k: list(v) for k, v in data.items()}
        except (json.JSONDecodeError, IOError, TypeError, ValueError):
            return {}

    def _persist(self) -> None:
        path = os.path.join(self._store_dir, self._index_file)
        with open(path, "w") as f:
            json.dump(self._index, f, default=str)


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity between two equal-length vectors."""
    import numpy as np

    va = np.asarray(a, dtype=float)
    vb = np.asarray(b, dtype=float)
    if va.size == 0 or vb.size == 0 or len(va) != len(vb):
        return 0.0
    denom = (np.linalg.norm(va) * np.linalg.norm(vb)) or 1e-12
    return float(np.dot(va, vb) / denom)