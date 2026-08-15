"""Chat API integration tests — ownership, persistence lifecycle, streaming,
model validation, duplicate requests, history from application persistence."""

from __future__ import annotations

import sys

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.services import chat_persistence as store


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Conversation CRUD + ownership
# ---------------------------------------------------------------------------

def test_create_conversation_and_send_message(client, alice_token, db, user, fake_graph):
    r = client.post("/chat", json={"session_id": "conv-1", "message": "hello"}, headers=_bearer(alice_token))
    assert r.status_code == 200
    assert r.json()["response"] == "invoked answer"

    conv = store.get_conversation(db, "conv-1", user.id)
    assert conv is not None
    assert conv.selected_model == "gpt-4o-mini"  # default model recorded
    roles = [(m.role, m.content) for m in store.list_messages(db, "conv-1")]
    assert roles == [("user", "hello"), ("assistant", "invoked answer")]
    # model flowed into the graph state
    assert fake_graph.last_invoke_state["model"] == "gpt-4o-mini"
    assert fake_graph.last_invoke_state["temperature"] == 0.7


def test_user_a_cannot_access_user_b_conversation(client, alice_token, bob_token, db, user, second_user):
    # Alice creates a conversation
    client.post("/chat", json={"session_id": "conv-secret", "message": "secret plan"}, headers=_bearer(alice_token))
    assert store.get_conversation(db, "conv-secret", user.id) is not None

    # Bob: every route must 404 (never reveal existence)
    assert client.get("/chat/conv-secret/history", headers=_bearer(bob_token)).status_code == 404
    assert client.patch("/chat/sessions/conv-secret", json={"title": "hacked"}, headers=_bearer(bob_token)).status_code == 404
    assert client.delete("/chat/sessions/conv-secret", headers=_bearer(bob_token)).status_code == 404
    assert client.post("/chat", json={"session_id": "conv-secret", "message": "intrude"}, headers=_bearer(bob_token)).status_code == 404
    assert client.post("/chat/stream", json={"session_id": "conv-secret", "message": "intrude"}, headers=_bearer(bob_token)).status_code == 404

    # Alice's data is untouched
    assert store.get_conversation(db, "conv-secret", user.id) is not None
    assert store.count_conversation_messages(db, "conv-secret") == 2


def test_list_sessions_is_owner_scoped(client, alice_token, bob_token, db):
    client.post("/chat", json={"session_id": "alice-conv", "message": "a"}, headers=_bearer(alice_token))
    client.post("/chat", json={"session_id": "bob-conv", "message": "b"}, headers=_bearer(bob_token))

    alice_list = client.get("/chat/sessions", headers=_bearer(alice_token)).json()
    bob_list = client.get("/chat/sessions", headers=_bearer(bob_token)).json()
    assert [s["id"] for s in alice_list["sessions"]] == ["alice-conv"]
    assert [s["id"] for s in bob_list["sessions"]] == ["bob-conv"]


def test_update_title_and_delete_owned_only(client, alice_token, bob_token, db, user):
    client.post("/chat", json={"session_id": "c1", "message": "hi"}, headers=_bearer(alice_token))
    r = client.patch("/chat/sessions/c1", json={"title": "Renamed", "is_pinned": True}, headers=_bearer(alice_token))
    assert r.status_code == 200
    assert r.json()["title"] == "Renamed"
    assert r.json()["is_pinned"] is True

    assert client.delete("/chat/sessions/c1", headers=_bearer(bob_token)).status_code == 404
    assert store.get_conversation(db, "c1", user.id) is not None

    assert client.delete("/chat/sessions/c1", headers=_bearer(alice_token)).status_code == 200
    assert store.get_conversation(db, "c1", user.id) is None
    assert store.count_conversation_messages(db, "c1") == 0


# ---------------------------------------------------------------------------
# History from application persistence
# ---------------------------------------------------------------------------

def test_history_returns_persisted_messages_ordered(client, alice_token, db, user):
    client.post("/chat", json={"session_id": "h1", "message": "q1"}, headers=_bearer(alice_token))
    client.post("/chat", json={"session_id": "h1", "message": "q2"}, headers=_bearer(alice_token))

    r = client.get("/chat/h1/history", headers=_bearer(alice_token))
    assert r.status_code == 200
    msgs = r.json()["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant"]
    assert msgs[1]["model"] == "gpt-4o-mini"
    assert msgs[1]["status"] == "completed"


def test_history_backfills_legacy_checkpoint_conversation(client, alice_token, db, user, fake_graph):
    """A legacy conversation with only checkpoint data gets backfilled once."""
    fake_graph.messages = [HumanMessage(content="old q"), AIMessage(content="old a")]

    r = client.get("/chat/legacy-1/history", headers=_bearer(alice_token))
    assert r.status_code == 200
    msgs = r.json()["messages"]
    assert [(m["role"], m["content"]) for m in msgs] == [("user", "old q"), ("assistant", "old a")]

    # Second load: no duplication (idempotent backfill)
    r2 = client.get("/chat/legacy-1/history", headers=_bearer(alice_token))
    assert len(r2.json()["messages"]) == 2

    # Sending a new message appends after backfilled history
    client.post("/chat", json={"session_id": "legacy-1", "message": "new q"}, headers=_bearer(alice_token))
    conv = store.get_conversation(db, "legacy-1", user.id)
    assert [m.content for m in store.list_messages(db, conv.id)] == ["old q", "old a", "new q", "invoked answer"]


# ---------------------------------------------------------------------------
# Model selection
# ---------------------------------------------------------------------------

def test_invalid_model_rejected_with_error_envelope(client, alice_token, db):
    r = client.post("/chat", json={"session_id": "m1", "message": "hi", "model": "gpt-99"}, headers=_bearer(alice_token))
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_generation_config"
    assert store.get_conversation(db, "m1", None) is None  # no conversation leaked


def test_temperature_out_of_bounds_rejected(client, alice_token):
    r = client.post("/chat", json={"session_id": "m2", "message": "hi", "temperature": 3.5}, headers=_bearer(alice_token))
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_generation_config"


def test_selected_model_reaches_llm_layer_and_is_recorded(client, alice_token, fake_graph, db):
    r = client.post("/chat", json={"session_id": "m3", "message": "hi", "model": "gpt-4o", "temperature": 1.5}, headers=_bearer(alice_token))
    assert r.status_code == 200
    assert fake_graph.last_invoke_state["model"] == "gpt-4o"
    assert fake_graph.last_invoke_state["temperature"] == 1.5
    rows = store.list_messages(db, "m3")
    assert {m.model for m in rows} == {"gpt-4o"}


# ---------------------------------------------------------------------------
# Streaming lifecycle
# ---------------------------------------------------------------------------

def _consume_stream(r):
    assert r.status_code == 200
    events = []
    for line in r.iter_lines():
        if line.startswith("data: "):
            events.append(line[6:])
    return events


def test_stream_success_persists_completed_assistant(client, alice_token, fake_graph, db):
    fake_graph.partial_chunks = ["Hel", "lo ", "world"]
    events = _consume_stream(client.post(
        "/chat/stream", json={"session_id": "s1", "message": "hi"}, headers=_bearer(alice_token)
    ))
    content = "".join(
        e[len("data: ") :] and (__import__("json").loads(e)["content"])
        for e in events if e != "[DONE]" and __import__("json").loads(e).get("type") == "content"
    )
    assert content == "Hello world"
    assert events[-1] == "[DONE]"

    rows = store.list_messages(db, "s1")
    assert [(m.role, m.status) for m in rows] == [("user", "completed"), ("assistant", "completed")]
    assert rows[1].content == "Hello world"
    assert rows[1].model == "gpt-4o-mini"


def test_stream_failure_before_output_persists_no_fake_assistant(client, alice_token, fake_graph, db):
    fake_graph.stream_error = RuntimeError("provider down")
    events = _consume_stream(client.post(
        "/chat/stream", json={"session_id": "s2", "message": "hi"}, headers=_bearer(alice_token)
    ))
    assert any("provider down" in e for e in events)
    rows = store.list_messages(db, "s2")
    assert [m.role for m in rows] == ["user"]  # NO fake assistant message


def test_stream_partial_failure_preserves_partial_marked_failed(client, alice_token, fake_graph, db):
    fake_graph.partial_chunks = ["Par", "tial"]
    fake_graph.stream_error = RuntimeError("timeout mid-stream")
    events = _consume_stream(client.post(
        "/chat/stream", json={"session_id": "s3", "message": "hi"}, headers=_bearer(alice_token)
    ))
    assert any("timeout mid-stream" in e for e in events)
    rows = store.list_messages(db, "s3")
    assert [(m.role, m.status, m.content) for m in rows] == [
        ("user", "completed", "hi"),
        ("assistant", "failed", "Partial"),
    ]


def test_stream_reaches_done_when_extraction_scheduled(client, alice_token, fake_graph, db, monkeypatch):
    """The real scheduling path (claim → bounded enqueue) runs off the stream
    thread; extraction must never delay or break the user-visible [DONE]."""
    calls: list[tuple] = []
    monkeypatch.setattr(
        sys.modules["app.learning.extraction.extractor"], "schedule_extraction",
        lambda *a, **k: calls.append(a),
    )
    fake_graph.partial_chunks = ["He", "llo"]
    events = _consume_stream(client.post(
        "/chat/stream", json={"session_id": "s4", "message": "hi"}, headers=_bearer(alice_token)
    ))
    assert events[-1] == "[DONE]"
    assert len(calls) == 1
    session_id, _user_id, _project_id, user_msg_id = calls[0]
    assert session_id == "s4"
    assert user_msg_id is not None  # turn identity (immutable message id), never a timestamp


def test_stream_clarification_persisted(client, alice_token, db, chat_module):
    class Conf:
        decision = "clarification"

    class Ctx:
        confidence = Conf()
        ranked_chunks = []
        trace = None
        answer_mode = "grounded"
        answer_mode_metadata = {}

    chat_module._pipeline.process = lambda *a, **k: Ctx()
    chat_module._pipeline.kb_not_covered_message = lambda: "Not covered."
    events = _consume_stream(client.post(
        "/chat/stream", json={"session_id": "s4", "message": "unknown topic"}, headers=_bearer(alice_token)
    ))
    rows = store.list_messages(db, "s4")
    assert [(m.role, m.content, m.status) for m in rows] == [
        ("user", "unknown topic", "completed"),
        ("assistant", "Not covered.", "completed"),
    ]


# ---------------------------------------------------------------------------
# Duplicate requests + concurrency notes
# ---------------------------------------------------------------------------

def test_duplicate_request_id_rejected_409(client, alice_token, db):
    body = {"session_id": "d1", "message": "hi", "request_id": "req-abc"}
    first = client.post("/chat", json=body, headers=_bearer(alice_token))
    assert first.status_code == 200
    second = client.post("/chat", json=body, headers=_bearer(alice_token))
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "duplicate_request"
    assert store.count_conversation_messages(db, "d1") == 2  # no duplicates


def test_rapid_sequential_messages_no_duplicates(client, alice_token, db):
    for i in range(3):
        r = client.post("/chat", json={"session_id": "r1", "message": f"msg {i}"}, headers=_bearer(alice_token))
        assert r.status_code == 200
    rows = store.list_messages(db, "r1")
    assert [m.content for m in rows] == ["msg 0", "invoked answer", "msg 1", "invoked answer", "msg 2", "invoked answer"]
    assert len({m.sequence for m in rows}) == 6


# ---------------------------------------------------------------------------
# Search scoped to owner
# ---------------------------------------------------------------------------

def test_search_scoped_to_owner(client, alice_token, bob_token):
    client.post("/chat", json={"session_id": "alice-secret", "message": "nuclear launch codes"}, headers=_bearer(alice_token))
    client.post("/chat", json={"session_id": "bob-secret", "message": "nuclear launch codes"}, headers=_bearer(bob_token))

    alice_results = client.get("/chat/search?q=nuclear", headers=_bearer(alice_token)).json()
    assert [r["session_id"] for r in alice_results["results"]] == ["alice-secret"]

    bob_results = client.get("/chat/search?q=nuclear", headers=_bearer(bob_token)).json()
    assert [r["session_id"] for r in bob_results["results"]] == ["bob-secret"]


# ---------------------------------------------------------------------------
# Auth enforcement on chat routes
# ---------------------------------------------------------------------------

def test_chat_requires_auth_when_no_single_user_fallback(client, db, monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "AUTH_ALLOW_SINGLE_USER_FALLBACK", False)
    assert client.get("/chat/sessions").status_code == 401
    assert client.post("/chat", json={"session_id": "x", "message": "y"}).status_code == 401


def test_chat_single_user_fallback_without_token(client, db, user, fake_graph, monkeypatch):
    """Single user exists → requests without a token are that user (opt-in)."""
    from app.core import config

    monkeypatch.setattr(config.settings, "AUTH_ALLOW_SINGLE_USER_FALLBACK", True)
    r = client.post("/chat", json={"session_id": "anon-1", "message": "hello"})
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Chat session project assignment (memory V2 projects)
# ---------------------------------------------------------------------------

def test_patch_session_project_id_persists(client, alice_token, db, user):
    from app.models.project import Project

    project = Project(owner_id=user.id, name="chat-project")
    db.add(project)
    db.commit()

    client.post("/chat", json={"session_id": "proj-1", "message": "hi"}, headers=_bearer(alice_token))
    r = client.patch("/chat/sessions/proj-1", json={"project_id": project.id}, headers=_bearer(alice_token))
    assert r.status_code == 200

    conv = store.get_conversation(db, "proj-1", user.id)
    assert conv is not None
    assert conv.project_id == project.id


def test_patch_session_foreign_project_404(client, alice_token, bob_token, db, user, second_user):
    from app.models.project import Project

    bob_project = Project(owner_id=second_user.id, name="bob-project")
    db.add(bob_project)
    db.commit()

    client.post("/chat", json={"session_id": "proj-2", "message": "hi"}, headers=_bearer(alice_token))
    r = client.patch("/chat/sessions/proj-2", json={"project_id": bob_project.id}, headers=_bearer(alice_token))
    assert r.status_code == 404

    conv = store.get_conversation(db, "proj-2", user.id)
    assert conv is not None
    assert conv.project_id is None