"""Unit tests for episodic conversation memory (cross-session recall).

Covers lazy consolidation (once per session), current-session exclusion,
evaluation-session exclusion, the similarity floor, and the summary artifact
shape (scope/source set by the consolidator).
"""

from __future__ import annotations

import pytest

from app.learning.operations.episodic import (
    EpisodicRecallService,
    SessionTranscript,
    load_recent_transcripts,
)
from app.learning.operations.memory import (
    SOURCE_CONSOLIDATION,
    session_scope,
)


def fake_embedder(texts):
    """Deterministic bag-of-words embeddings — related text shares tokens."""
    vocab = {
        "discussed", "building", "chat", "parser", "rag", "pipeline",
        "prefers", "kotlin", "project", "refactor", "retriever", "deploy",
    }
    return [[1.0 if token in t.lower() else 0.0 for token in vocab] for t in texts]


def test_load_recent_transcripts_filters_current_and_eval():
    transcripts = [
        SessionTranscript("sess-a", messages=[("user", "hi"), ("assistant", "hello")]),
        SessionTranscript("sess-b", messages=[("user", "hi"), ("assistant", "hello")]),
        SessionTranscript("eval-run-1", messages=[("user", "x"), ("assistant", "y")]),
    ]

    result = load_recent_transcripts(lambda limit: transcripts, session_id="sess-a")

    assert [t.session_id for t in result] == ["sess-b"]


def test_consolidates_missing_sessions_on_first_recall(tmp_path):
    transcripts = [
        SessionTranscript(
            "sess-a",
            title="parser work",
            messages=[
                ("user", "remember in this conversation we are building a chat parser"),
                ("assistant", "noted"),
            ],
        ),
        SessionTranscript(
            "sess-b",
            title="kotlin preference",
            messages=[
                ("user", "i prefer kotlin for side projects"),
                ("assistant", "good to know"),
            ],
        ),
    ]
    summaries = ["we discussed building a chat parser", "the user prefers kotlin"]
    service = EpisodicRecallService(
        store_dir=str(tmp_path),
        session_loader=lambda limit: transcripts,
        summarize_fn=lambda ts: summaries[: len(ts)],
        embed_fn=fake_embedder,
        min_score=0.25,
        min_transcript_messages=2,
    )

    top = service.recall("what are we building?", session_id="sess-new")

    assert len(top) == 1
    assert "chat parser" in top[0].fact
    # summary artifact shape: consolidation source, session scope of the origin conversation
    assert top[0].source == SOURCE_CONSOLIDATION
    assert top[0].scope == session_scope("sess-a")
    assert top[0].id.startswith("mem-")
    assert top[0].supersedes == []


def test_same_session_not_summarized_twice(tmp_path):
    transcripts = [
        SessionTranscript(
            "sess-a",
            title="parser work",
            messages=[("user", "we are building a chat parser"), ("assistant", "ok")],
        )
    ]
    summarize_calls = []

    def counting_summarizer(ts):
        summarize_calls.append(len(ts))
        return ["we discussed building a chat parser"] * len(ts)

    service = EpisodicRecallService(
        store_dir=str(tmp_path),
        session_loader=lambda limit: transcripts,
        summarize_fn=counting_summarizer,
        embed_fn=fake_embedder,
        min_score=0.25,
        min_transcript_messages=2,
    )

    first = service.recall("what are we building?", session_id="sess-new")
    second = service.recall("what are we building?", session_id="sess-new")

    assert first and second
    assert summarize_calls == [1]  # consolidation ran exactly once
    from app.learning.operations.memory import MemoryStore
    assert len(MemoryStore(store_dir=str(tmp_path)).list_all()) == 1


def test_recall_excludes_current_session_summaries(tmp_path):
    transcripts = [
        SessionTranscript(
            "sess-a",
            title="parser work",
            messages=[("user", "we are building a chat parser"), ("assistant", "ok")],
        )
    ]
    service = EpisodicRecallService(
        store_dir=str(tmp_path),
        session_loader=lambda limit: transcripts,
        summarize_fn=lambda ts: ["we discussed building a chat parser"] * len(ts),
        embed_fn=fake_embedder,
        min_score=0.25,
        min_transcript_messages=2,
    )

    # asking from within the session being summarized must NOT surface its own summary
    top = service.recall("what are we building?", session_id="sess-a")

    assert top == []


def test_recall_returns_empty_when_summaries_irrelevant(tmp_path):
    transcripts = [
        SessionTranscript(
            "sess-a",
            title="cooking",
            messages=[("user", "i like italian food"), ("assistant", "nice")],
        )
    ]
    service = EpisodicRecallService(
        store_dir=str(tmp_path),
        session_loader=lambda limit: transcripts,
        summarize_fn=lambda ts: ["the user likes italian food"] * len(ts),
        embed_fn=fake_embedder,
        min_score=0.25,
        min_transcript_messages=2,
    )

    top = service.recall("what are we building?", session_id="sess-new")

    assert top == []


def test_recall_with_empty_query_returns_nothing(tmp_path):
    service = EpisodicRecallService(
        store_dir=str(tmp_path),
        session_loader=lambda limit: [],
        summarize_fn=lambda ts: [],
        embed_fn=fake_embedder,
    )

    assert service.recall("   ", session_id="sess-new") == []


def test_empty_and_short_transcripts_not_summarized(tmp_path):
    transcripts = [
        SessionTranscript("sess-a", title="t", messages=[("user", "hi")]),
        SessionTranscript("sess-b", title="", messages=[]),
    ]
    summarize_calls = []

    def spy(ts):
        summarize_calls.append(len(ts))
        return []

    service = EpisodicRecallService(
        store_dir=str(tmp_path),
        session_loader=lambda limit: transcripts,
        summarize_fn=spy,
        embed_fn=fake_embedder,
        min_transcript_messages=2,
    )

    service.recall("what are we building?", session_id="sess-new")

    assert summarize_calls == []  # nothing substantial to consolidate


def test_recall_only_transcripts_are_not_summarized(tmp_path):
    """'what are we building?' style sessions are memory exercises, not content."""
    transcripts = [
        SessionTranscript(
            "sess-meta",
            title="asking for my name",
            messages=[
                ("user", "what are we building?"),
                ("assistant", "I don't have that information"),
                ("user", "what is my name?"),
                ("assistant", "I don't know"),
            ],
        ),
        SessionTranscript(
            "sess-real",
            title="parser work",
            messages=[
                ("user", "remember in this conversation we are building a chat parser"),
                ("assistant", "noted"),
                ("user", "we chose python for it"),
                ("assistant", "got it"),
            ],
        ),
    ]
    summarize_calls = []

    def spy(ts):
        summarize_calls.append([t.session_id for t in ts])
        return ["we discussed building a chat parser"] * len(ts)

    service = EpisodicRecallService(
        store_dir=str(tmp_path),
        session_loader=lambda limit: transcripts,
        summarize_fn=spy,
        embed_fn=fake_embedder,
    )

    top = service.recall("what are we building?", session_id="sess-new")

    # only the real conversation was consolidated (4+ msgs, not recall-only)
    assert summarize_calls == [["sess-real"]]
    assert top and "chat parser" in top[0].fact


def test_summarizer_failure_creates_no_artifacts(tmp_path):
    transcripts = [
        SessionTranscript(
            "sess-a",
            title="parser work",
            messages=[("user", "we are building a chat parser"), ("assistant", "ok")],
        )
    ]

    def failing_summarizer(ts):
        return [""]  # empty output — treated as failure

    service = EpisodicRecallService(
        store_dir=str(tmp_path),
        session_loader=lambda limit: transcripts,
        summarize_fn=failing_summarizer,
        embed_fn=fake_embedder,
        min_transcript_messages=2,
    )

    top = service.recall("what are we building?", session_id="sess-new")

    assert top == []
    from app.learning.operations.memory import MemoryStore
    assert MemoryStore(store_dir=str(tmp_path)).list_all() == []


def test_newest_summary_per_session_wins(tmp_path):
    """Multiple summaries of one session: recall uses the newest one."""
    service = EpisodicRecallService(
        store_dir=str(tmp_path),
        session_loader=lambda limit: [],
        summarize_fn=lambda ts: [],
        embed_fn=fake_embedder,
    )
    from app.learning.operations.memory import MemoryStore

    store = MemoryStore(store_dir=str(tmp_path))
    store.store_fact("old summary about the parser", scope=session_scope("sess-a"), source=SOURCE_CONSOLIDATION)
    store.store_fact("newer summary: we discussed building a chat parser", scope=session_scope("sess-a"), source=SOURCE_CONSOLIDATION)

    top = service.recall("what are we building?", session_id="sess-new")

    assert len(top) == 1
    assert "newer summary" in top[0].fact