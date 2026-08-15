"""Unit tests for the structured semantic memory store.

Covers artifact immutability, scoping, dedupe, the append-only
forget/supersede lifecycle, and the vectored recall index.
"""

from __future__ import annotations

import pytest

from app.learning.operations.memory import (
    MemoryStore,
    MemoryFact,
    MemoryEmbeddingIndex,
    cosine_similarity,
    SCOPE_GLOBAL,
    session_scope,
    STATUS_ACTIVE,
    STATUS_SUPERSEDED,
    SOURCE_TOOL_CALL,
)


@pytest.fixture
def store(tmp_path):
    return MemoryStore(store_dir=str(tmp_path))


def test_store_fact_creates_artifact(store):
    fact = store.store_fact("My name is Alice", source=SOURCE_TOOL_CALL)

    assert fact.id.startswith("mem-")
    assert fact.status == STATUS_ACTIVE
    assert fact.version == 1
    assert fact.scope == SCOPE_GLOBAL
    assert fact.created_at
    # persisted artifact is readable and round-trips
    loaded = store.get(fact.id)
    assert loaded is not None
    assert loaded.fact == fact.fact
    assert loaded.to_dict()["events"][0]["status"] == "stored"


def test_identical_fact_is_idempotent(store):
    first = store.store_fact("My name is Alice")
    second = store.store_fact("My name is Alice")

    assert second.id == first.id
    assert len(store.list_active()) == 1


def test_fact_normalization_dedupes_whitespace_and_case(store):
    first = store.store_fact("  My Name Is Alice  ")
    second = store.store_fact("my name is alice")

    assert second.id == first.id
    assert first.fact == "my name is alice"


def test_scope_isolation(store):
    global_fact = store.store_fact("user prefers concise answers")
    session_fact = store.store_fact("we discussed the RAG design", scope=session_scope("sess-1"))

    assert len(store.list_active(scope=SCOPE_GLOBAL)) == 1
    assert len(store.list_active(scope=session_scope("sess-1"))) == 1
    assert store.list_active(scope=session_scope("sess-2")) == []

    # identical text in different scopes is NOT deduped
    other = store.store_fact("user prefers concise answers", scope=session_scope("sess-9"))
    assert other.id != global_fact.id


def test_session_prefix_scope_filter(store):
    store.store_fact("global fact")
    store.store_fact("sess-1 fact", scope=session_scope("sess-1"))
    store.store_fact("sess-2 fact", scope=session_scope("sess-2"))

    session_facts = store.list_active(scope="session")
    assert len(session_facts) == 2
    assert all(f.scope.startswith("session:") for f in session_facts)


def test_same_scope_dedupe_across_scopes_of_same_session(store):
    first = store.store_fact("todo: refactor retriever", scope=session_scope("sess-1"))
    second = store.store_fact("todo: refactor retriever", scope=session_scope("sess-1"))
    assert second.id == first.id


def test_forget_supersedes_append_only(store):
    fact = store.store_fact("user's favorite color is blue")
    assert fact.status == STATUS_ACTIVE

    updated = store.forget(fact.id, operator="ops-user")
    assert updated is not None
    assert updated.status == STATUS_SUPERSEDED
    assert updated.fact == fact.fact  # content preserved, never rewritten
    assert updated.events[-1].status == STATUS_SUPERSEDED
    assert "ops-user" in updated.events[-1].note

    assert store.list_active() == []
    assert len(store.list_superseded()) == 1

    # forgetting twice is a no-op transition-wise
    again = store.forget(fact.id, operator="ops-user")
    assert again.status == STATUS_SUPERSEDED
    assert len(again.events) == 2  # one stored + one superseded


def test_forget_unknown_returns_none(store):
    assert store.forget("mem-unknown") is None


def test_find_active_fact_by_text_and_scope(store):
    store.store_fact("prefers kotlin", scope=SCOPE_GLOBAL)
    store.store_fact("prefers kotlin", scope=session_scope("sess-1"))

    assert store.find_active_fact("Prefers Kotlin") is not None          # global hit
    assert store.find_active_fact("prefers kotlin", scope=session_scope("sess-1")) is not None
    assert store.find_active_fact("prefers kotlin", scope=session_scope("sess-2")) is None
    assert store.find_active_fact("no such fact") is None


def test_forget_session_scoped_fact(store):
    fact = store.store_fact("we discussed the parser", scope=session_scope("sess-1"))
    store.forget(fact.id, operator="agent_tool", note="via tool")

    assert store.list_active(scope=session_scope("sess-1")) == []
    assert len(store.list_superseded(scope=session_scope("sess-1"))) == 1


def test_empty_fact_rejected(store):
    with pytest.raises(ValueError):
        store.store_fact("   ")


def test_ordering_newest_first(store):
    store.store_fact("fact one")
    store.store_fact("fact two")
    store.store_fact("fact three")

    facts = store.list_active()
    assert [f.fact for f in facts] == ["fact three", "fact two", "fact one"]


def test_artifact_has_lineage_fields():
    fact = MemoryFact(fact="x", supersedes=["mem-parent"])
    assert fact.supersedes == ["mem-parent"]
    assert fact.id
    assert fact.created_at
    assert fact.version >= 1


# ── Vectored recall index ───────────────────────────────────────────────


def fake_embedder(texts):
    """Deterministic bag-of-words embeddings — related text shares tokens."""
    vocab = {"name", "alice", "prefers", "concise", "answers", "python", "project"}
    vectors = []
    for text in texts:
        v = [0.0] * len(vocab)
        for i, token in enumerate(vocab):
            if token in text.lower():
                v[i] = 1.0
        vectors.append(v)
    return vectors


@pytest.fixture
def index_store(tmp_path):
    return MemoryStore(store_dir=str(tmp_path))


@pytest.fixture
def index(tmp_path):
    return MemoryEmbeddingIndex(store_dir=str(tmp_path), embed_fn=fake_embedder)


def test_index_selects_relevant_facts(index, index_store):
    index_store.store_fact("user's name is alice")
    index_store.store_fact("user prefers concise answers")
    index_store.store_fact("works on a python project")
    facts = index_store.list_active(scope=SCOPE_GLOBAL)

    top = index.select_for_query("what is my name?", facts, k=2)

    assert top[0].fact == "user's name is alice"
    assert len(top) == 2


def test_index_returns_all_when_small(index, index_store):
    index_store.store_fact("a single fact")
    facts = index_store.list_active()
    assert index.select_for_query("irrelevant", facts, k=5) == facts


def test_index_min_score_filters_unrelated_facts(index, index_store):
    index_store.store_fact("user's name is alice")
    facts = index_store.list_active()

    assert index.select_for_query("unrelated topic", facts, k=5, min_score=0.5) == []
    assert len(index.select_for_query("what is my name?", facts, k=5, min_score=0.5)) == 1


def test_index_persists_across_instances(tmp_path, index_store):
    index_store.store_fact("user's name is alice")
    first = MemoryEmbeddingIndex(store_dir=str(tmp_path), embed_fn=fake_embedder)
    first.select_for_query("name", index_store.list_active(), k=5)

    # A fresh instance loads the persisted sidecar — embed_fn must NOT be called
    calls = []
    def counting_embedder(texts):
        calls.append(texts)
        return fake_embedder(texts)

    second = MemoryEmbeddingIndex(store_dir=str(tmp_path), embed_fn=counting_embedder)
    facts = index_store.list_active()
    top = second.select_for_query("name", facts, k=5)
    assert top[0].fact == "user's name is alice"
    # fact embeddings came from the persisted index — only the query gets embedded
    assert calls == [["name"]]


def test_index_skips_facts_without_embeddings(index, index_store):
    index_store.store_fact("fact one")
    facts = index_store.list_active()
    top = index.select_for_query("fact one", facts, k=5)
    assert len(top) == 1  # only the embedded fact is returned


def test_embedding_index_not_treated_as_memory_fact(tmp_path, index_store):
    """The .memory_index.json sidecar must never break fact scanning."""
    index_store.store_fact("real fact")
    first = MemoryEmbeddingIndex(store_dir=str(tmp_path), embed_fn=fake_embedder)
    first.select_for_query("real", index_store.list_active(), k=5)

    assert index_store.list_active()[0].fact == "real fact"
    assert len(index_store.list_all()) == 1


def test_forgot_facts_are_excluded_from_recall(index, index_store):
    index_store.store_fact("user's name is alice")
    index_store.store_fact("user prefers concise answers")
    fact = index_store.find_active_fact("user's name is alice")
    index_store.forget(fact.id, operator="tester")

    active = index_store.list_active(scope=SCOPE_GLOBAL)
    top = index.select_for_query("what is my name?", active, k=5)
    assert all(f.fact != "user's name is alice" for f in top)


def test_cosine_similarity():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine_similarity([], []) == 0.0
    assert cosine_similarity([1.0], [1.0, 0.0]) == 0.0
