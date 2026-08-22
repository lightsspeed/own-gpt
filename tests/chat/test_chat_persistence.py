"""Chat persistence service tests — the canonical application chat database."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.services import chat_persistence as store
from app.services.auth import create_user


@pytest.fixture
def owner(db):
    return create_user(db, "owner", "password123")


def _make_conversation(db, owner, cid="conv-1", title="t"):
    return store.create_conversation(db, owner, cid, title=title, selected_model="gpt-4o-mini")


def test_create_and_get_conversation_owned(db, owner):
    conv = _make_conversation(db, owner)
    assert conv.owner_id == owner.id
    assert conv.thread_id == conv.id  # explicit conversation.id -> thread_id mapping
    fetched = store.get_conversation(db, conv.id, owner.id)
    assert fetched is not None
    assert fetched.title == "t"


def test_get_conversation_enforces_ownership(db, owner):
    conv = _make_conversation(db, owner)
    other = create_user(db, "intruder", "password123")
    assert store.get_conversation(db, conv.id, other.id) is None


def test_list_conversations_scoped_to_owner(db, owner):
    _make_conversation(db, owner, "c1")
    other = create_user(db, "other", "password123")
    _make_conversation(db, other, "c2")
    sessions = store.list_conversations(db, owner)
    assert [s.id for s in sessions] == ["c1"]


def test_message_ordering_deterministic(db, owner):
    conv = _make_conversation(db, owner)
    m1 = store.persist_user_message(db, conv, "first", "gpt-4o-mini")
    m2 = store.persist_assistant_message(db, conv, "reply", "gpt-4o-mini")
    m3 = store.persist_user_message(db, conv, "second", "gpt-4o-mini")
    m4 = store.persist_assistant_message(db, conv, "reply2", "gpt-4o-mini")
    seqs = [m.sequence for m in [m1, m2, m3, m4]]
    assert seqs == [1, 2, 3, 4]
    listed = store.list_messages(db, conv.id)
    assert [m.content for m in listed] == ["first", "reply", "second", "reply2"]


def test_message_ordering_under_concurrency_like_inserts(db, owner):
    """Two interleaved transaction attempts must still yield unique sequences."""
    conv = _make_conversation(db, owner)
    for i in range(6):
        store.persist_user_message(db, conv, f"msg-{i}", "gpt-4o-mini")
    seqs = [m.sequence for m in store.list_messages(db, conv.id)]
    assert seqs == [1, 2, 3, 4, 5, 6]
    assert len(set(seqs)) == 6


def test_conversation_isolation(db, owner):
    conv_a = _make_conversation(db, owner, "A")
    conv_b = _make_conversation(db, owner, "B")
    store.persist_user_message(db, conv_a, "A1", None)
    store.persist_user_message(db, conv_b, "B1", None)
    store.persist_user_message(db, conv_b, "B2", None)
    a_msgs = store.list_messages(db, "A")
    b_msgs = store.list_messages(db, "B")
    assert [m.content for m in a_msgs] == ["A1"]
    assert [m.content for m in b_msgs] == ["B1", "B2"]


def test_assistant_model_recorded(db, owner):
    conv = _make_conversation(db, owner)
    store.persist_user_message(db, conv, "q", "gpt-4o-mini")
    msg = store.persist_assistant_message(db, conv, "a", "deepseek-chat")
    assert msg.model == "deepseek-chat"
    assert msg.status == store.MESSAGE_STATUS_COMPLETED


def test_failed_assistant_message_not_silently_successful(db, owner):
    conv = _make_conversation(db, owner)
    msg = store.persist_assistant_message(
        db, conv, "partial", "gpt-4o-mini", status=store.MESSAGE_STATUS_FAILED, error="boom"
    )
    assert msg.status == "failed"
    assert msg.error == "boom"


def test_request_id_idempotency(db, owner):
    conv = _make_conversation(db, owner)
    first = store.persist_user_message(db, conv, "hello", None, request_id="req-1")
    second = store.persist_user_message(db, conv, "hello", None, request_id="req-1")
    assert first.id == second.id
    assert store.count_conversation_messages(db, conv.id) == 1
    # different request_id → new row
    third = store.persist_user_message(db, conv, "hello again", None, request_id="req-2")
    assert third.id != first.id
    assert store.count_conversation_messages(db, conv.id) == 2


def test_backfill_from_checkpoint_idempotent(db, owner):
    conv = _make_conversation(db, owner)
    checkpoint_msgs = [
        HumanMessage(content="legacy question"),
        AIMessage(content="legacy answer"),
        ToolMessage(content="tool result", tool_call_id="x"),
    ]
    n = store.backfill_messages_from_checkpoint(db, conv, checkpoint_msgs)
    assert n == 2  # tool messages skipped
    msgs = store.list_messages(db, conv.id)
    assert [m.role for m in msgs] == ["user", "assistant"]
    assert [m.content for m in msgs] == ["legacy question", "legacy answer"]
    assert all(m.additional_kwargs.get("backfilled") for m in msgs)

    # Idempotent: second backfill is a no-op once rows exist
    n2 = store.backfill_messages_from_checkpoint(db, conv, checkpoint_msgs)
    assert n2 == 0
    assert store.count_conversation_messages(db, conv.id) == 2

    # New messages append after backfilled ones
    store.persist_user_message(db, conv, "new question", "gpt-4o-mini")
    seqs = [m.sequence for m in store.list_messages(db, conv.id)]
    assert seqs == [1, 2, 3]


def test_delete_conversation_cascades_messages(db, owner):
    conv = _make_conversation(db, owner)
    store.persist_user_message(db, conv, "q", None)
    store.persist_assistant_message(db, conv, "a", None)
    store.delete_conversation(db, conv)
    assert store.get_conversation(db, conv.id, owner.id) is None
    assert store.count_conversation_messages(db, conv.id) == 0


def test_legacy_ownerless_conversation_invisible_to_users(db, owner):
    """Pre-V1.1 rows have owner_id NULL → invisible to every owner query."""
    from app.models.chat import ChatSession

    legacy = ChatSession(id="legacy-1", title="old", thread_id="legacy-1")
    db.add(legacy)
    db.commit()
    assert store.get_conversation(db, "legacy-1", owner.id) is None


def test_search_messages_only_returns_owned(db, owner):
    conv = _make_conversation(db, owner, "mine")
    store.persist_user_message(db, conv, "kubernetes networking", None)
    other = create_user(db, "other2", "password123")
    conv2 = _make_conversation(db, other, "theirs")
    store.persist_user_message(db, conv2, "kubernetes secrets", None)

    hits = store.search_messages(db, owner, "kubernetes")
    assert [h.session_id for h in hits] == ["mine"]