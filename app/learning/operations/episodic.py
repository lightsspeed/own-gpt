"""Episodic memory — cross-session conversation recall.

Past conversations become durable summary artifacts (MemoryFact with
source="consolidation", scope "session:<id>") persisted in episodic_summaries/ —
a directory parallel to memory_facts, reusing the MemoryStore/MemoryEmbeddingIndex
machinery so summaries get the same immutable-artifact and indexing guarantees.

Summarization is lazy: the first recall that needs recent conversations triggers
consolidation of the most recent sessions that do not yet have summaries (LLM,
capped per call). Summaries are then embedded and retrieved by cosine similarity.
Nothing is injected into the prompt unless a summary clears the similarity floor
(min_score), so unrelated queries never inherit stale conversation context.

Recall path (wired in the agent graph): a memory-intent query arrives in a
session that has no facts of its own →
    EpisodicRecallService.recall(query_text, session_id)
      1. load active summaries for OTHER sessions (newest per session)
      2. lazily consolidate recent sessions lacking a summary (capped)
      3. vector-select top-k above min_score
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Callable, Optional

from app.core.config import settings
from app.learning.operations.memory import (
    MemoryEmbeddingIndex,
    MemoryFact,
    MemoryStore,
    SOURCE_CONSOLIDATION,
    session_scope,
)

logger = logging.getLogger(__name__)

EPISODIC_DIR = "episodic_summaries"
EPISODIC_INDEX_FILE = ".episodic_index.json"


@dataclass
class SessionTranscript:
    """Immutable view of a past conversation, fed to the consolidator."""
    session_id: str
    title: str = ""
    messages: list[tuple[str, str]] = field(default_factory=list)

    def is_substantial(self, min_messages: int = 2, max_messages: int = 50) -> bool:
        """A conversation worth summarizing (has real turns, bounded in size)."""
        return min_messages <= len(self.messages) <= max_messages

    def render(self) -> str:
        return "\n".join(f"{role.title()}: {content}" for role, content in self.messages)


def load_recent_transcripts(
    session_loader: Callable[[int], list[SessionTranscript]],
    session_id: str,
    exclude_eval: bool = True,
) -> list[SessionTranscript]:
    """Transcripts for sessions other than the current one."""
    transcripts: list[SessionTranscript] = []
    for transcript in session_loader(20):
        if transcript.session_id == session_id:
            continue
        if exclude_eval and transcript.session_id.startswith("eval-"):
            continue
        transcripts.append(transcript)
    return transcripts


def default_session_loader(limit: int = 8, user_id: str = "") -> list[SessionTranscript]:
    """Load recent conversation transcripts from application chat persistence.

    chat_messages (PostgreSQL) is the canonical conversation history — not
    LangGraph checkpoint blobs. Reading here keeps memory consolidation
    aligned with what the user actually sees.

    Tenant isolation invariant (V2.2): when user_id is provided, ONLY that
    user's sessions are loaded — cross-tenant transcript leakage is impossible.
    """
    try:
        from sqlalchemy import select
        from app.core.database import SyncSessionLocal
        from app.models.chat import ChatMessage, ChatSession

        with SyncSessionLocal() as db:
            q = select(ChatSession).order_by(ChatSession.updated_at.desc()).limit(limit)
            if user_id:
                q = q.where(ChatSession.owner_id == user_id)
            sessions = list(db.execute(q).scalars())
            transcripts: list[SessionTranscript] = []
            for session in sessions:
                messages = list(
                    db.execute(
                        select(ChatMessage)
                        .where(ChatMessage.session_id == session.id)
                        .order_by(ChatMessage.sequence.asc())
                    ).scalars()
                )
                pairs = [
                    (m.role, m.content)
                    for m in messages
                    if m.role in ("user", "assistant") and m.content and m.status != "failed"
                ]
                if pairs:
                    transcripts.append(
                        SessionTranscript(session_id=session.id, title=session.title, messages=pairs)
                    )
            return transcripts
    except Exception as exc:
        logger.warning("episodic_transcript_load_failed: %s", exc)
        return []


def default_summarize(transcripts: list[SessionTranscript]) -> list[str]:
    """Consolidate transcripts into 2-3 sentence summaries (one per transcript)."""
    from langchain_openai import ChatOpenAI  # deferred — heavy import

    model = ChatOpenAI(model=settings.DEFAULT_MODEL, temperature=0.0, openai_api_key=settings.OPENAI_API_KEY)
    results: list[str] = []
    for transcript in transcripts:
        prompt = (
            "You are a memory consolidation service. Summarize the conversation below in 2-3 concise sentences:\n"
            "- capture the main topic, decisions, and user-stated facts (names, preferences, goals)\n"
            "- output ONLY the summary text, no preamble\n\n"
            f"{transcript.render()}"
        )
        try:
            reply = model.invoke(prompt)
            summary = reply.content.strip()
            if summary:
                results.append(summary)
        except Exception as exc:
            logger.warning("episodic_summarize_failed session=%s: %s", transcript.session_id, exc)
            results.append("")
    return results


class EpisodicRecallService:
    """Retrieves and consolidates cross-session conversation summaries.

    All collaborators are injectable for deterministic tests; the defaults
    consult the platform database and the LLM.
    """

    def __init__(
        self,
        store_dir: str = EPISODIC_DIR,
        session_loader: Optional[Callable[[int], list[SessionTranscript]]] = None,
        summarize_fn: Optional[Callable[[list[SessionTranscript]], list[str]]] = None,
        embed_fn: Optional[Callable[[list[str]], list[list[float]]]] = None,
        k: int = 2,
        min_score: float = 0.25,
        max_new_summaries: int = 3,
        min_transcript_messages: int = 4,
        max_transcript_messages: int = 50,
        exclude_eval: bool = True,
        user_id: str = "",
    ):
        self._store_dir = store_dir
        self._session_loader = session_loader or default_session_loader
        self._summarize_fn = summarize_fn or default_summarize
        self._embed_fn = embed_fn
        self._k = k
        self._min_score = min_score
        self._max_new_summaries = max_new_summaries
        self._min_transcript_messages = min_transcript_messages
        self._max_transcript_messages = max_transcript_messages
        self._exclude_eval = exclude_eval
        self._user_id = user_id

    # ── Public ──────────────────────────────────────────────────────────────

    def recall(self, query: str, session_id: str = "", user_id: str = "") -> list[MemoryFact]:
        """Top-k summaries of past conversations relevant to the query.

        Returns [] when nothing clears the similarity floor or recall is
        impossible (empty query, no other sessions). With user_id provided,
        transcripts are tenant-scoped to that user (D4 invariant).
        """
        query = (query or "").strip()
        if user_id:
            self._user_id = user_id
        current_scope = session_scope(session_id) if session_id else ""
        store = MemoryStore(store_dir=self._store_dir)

        self._consolidate_missing(store, current_scope)
        candidates = self._active_summaries(store, exclude_scope=current_scope)
        if not candidates or not query:
            return []

        index = MemoryEmbeddingIndex(
            store_dir=self._store_dir,
            embed_fn=self._embed_fn,
            index_file=EPISODIC_INDEX_FILE,
        )
        return index.select_for_query(query, candidates, k=self._k, min_score=self._min_score)

    # ── Internals ───────────────────────────────────────────────────────────

    def _consolidate_missing(self, store: MemoryStore, current_scope: str) -> None:
        """Summarize the most recent conversations that lack summaries (capped).

        Idempotent: sessions that already have an active summary are skipped,
        and summarize_fn failures produce no artifacts.
        """
        existing = {fact.scope for fact in self._active_summaries(store)}
        transcripts = self._load_transcripts()
        missing = [
            t
            for t in transcripts
            if session_scope(t.session_id) not in existing
            and session_scope(t.session_id) != current_scope
        ]
        missing = missing[: self._max_new_summaries]
        if not missing:
            return

        summaries = self._summarize_fn(missing)
        for transcript, summary in zip(missing, summaries):
            summary = (summary or "").strip()
            if not summary:
                continue
            store.store_fact(
                summary,
                scope=session_scope(transcript.session_id),
                source=SOURCE_CONSOLIDATION,
                note="episodic consolidation",
            )

    def _load_transcripts(self) -> list[SessionTranscript]:
        loader = self._session_loader
        if loader is default_session_loader and self._user_id:
            loader = lambda limit: default_session_loader(limit, user_id=self._user_id)
        transcripts = load_recent_transcripts(loader, "", self._exclude_eval)
        return [
            t
            for t in transcripts
            if t.is_substantial(self._min_transcript_messages, self._max_transcript_messages)
            and not self._is_recall_only(t)
        ]

    @staticmethod
    def _is_recall_only(transcript: SessionTranscript) -> bool:
        """A conversation whose first user message is a memory-recall question.

        Sessions like "what is my name?" or "what are we building?" are memory
        exercises, not content worth recalling — the platform already answers
        them from live memory (global/session facts or other summaries).
        Deterministic rule-only classification; no LLM involved.
        """
        if not transcript.messages or not transcript.messages[0][0] == "user":
            return False
        first = transcript.messages[0][1].strip().lower()
        if not first.endswith("?"):
            return False
        from app.agent.pipeline.intent import IntentClassifier  # deferred import

        result = IntentClassifier().rule_classify(first)
        if result is None:
            return False
        return result.intent.value == "memory"

    def _active_summaries(self, store: MemoryStore, exclude_scope: str = "") -> list[MemoryFact]:
        """Newest active summary per session, excluding the current scope."""
        newest_by_scope: dict[str, MemoryFact] = {}
        for fact in store.list_active(scope=None):  # newest first
            if exclude_scope and fact.scope == exclude_scope:
                continue
            newest_by_scope.setdefault(fact.scope, fact)
        return list(newest_by_scope.values())