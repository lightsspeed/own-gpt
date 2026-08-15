"""retrieve_memory node (V2.2) tests — hermetic, no PostgreSQL, no network.

The real app.agent.graph module is imported with a fake app.services.vector_store
pre-installed (mirrors tests/chat/conftest.py) so PGVector/OpenAIEmbeddings
clients are never constructed at import time. The node's collaborators
(_search_memories, _build_embedding_provider) are monkeypatched.
"""

from __future__ import annotations

import sys
import types

import pytest
from langchain_core.messages import HumanMessage

from app.core.config import settings


@pytest.fixture
def graph_module():
    real = sys.modules.get("app.services.vector_store")
    fake = types.ModuleType("app.services.vector_store")
    fake.vector_store = object()
    fake.embeddings = object()
    fake.similarity_search = lambda *a, **k: []
    fake.add_documents_to_store = lambda *a, **k: None
    sys.modules["app.services.vector_store"] = fake

    import app.agent.graph as gm

    yield gm

    if real is not None:
        sys.modules["app.services.vector_store"] = real
    else:
        sys.modules.pop("app.services.vector_store", None)


def _hit(statement: str):
    from types import SimpleNamespace

    return type("Hit", (), {"entity": SimpleNamespace(statement=statement)})()


def test_retrieve_memory_flag_off_returns_empty(monkeypatch, graph_module):
    monkeypatch.setattr(settings, "MEMORY_V2_GRAPH", False)
    state = {
        "messages": [HumanMessage(content="what should I know?")],
        "user_id": "u1",
        "project_id": "p1",
    }
    out = graph_module.retrieve_memory(state)
    assert out == {"memory_context": ""}


def test_retrieve_memory_injects_ranked_facts(monkeypatch, graph_module):
    monkeypatch.setattr(settings, "MEMORY_V2_GRAPH", True)
    captured = {}

    def fake_search(db, user_id, query, project_id=None, k=5, max_tokens=None, embed=None):
        captured["user_id"] = user_id
        captured["project_id"] = project_id
        captured["query"] = query
        captured["k"] = k
        captured["max_tokens"] = max_tokens
        return [_hit("the user prefers kotlin"), _hit("the user works at acme")]

    monkeypatch.setattr(graph_module, "_search_memories", fake_search)
    from types import SimpleNamespace

    monkeypatch.setattr(
        graph_module, "_build_embedding_provider",
        lambda: SimpleNamespace(embed=lambda texts: []),
    )

    state = {
        "messages": [HumanMessage(content="what do you remember about me?")],
        "user_id": "u1",
        "project_id": "p1",
    }
    out = graph_module.retrieve_memory(state)

    assert captured == {
        "user_id": "u1",
        "project_id": "p1",
        "query": "what do you remember about me?",
        "k": 5,
        "max_tokens": 400,
    }
    assert "the user prefers kotlin" in out["memory_context"]
    assert "the user works at acme" in out["memory_context"]


def test_retrieve_memory_no_identity_returns_empty(monkeypatch, graph_module):
    monkeypatch.setattr(settings, "MEMORY_V2_GRAPH", True)
    monkeypatch.setattr(graph_module, "_search_memories", lambda **k: [_hit("x")])
    state = {"messages": [HumanMessage(content="hi")], "user_id": ""}
    assert graph_module.retrieve_memory(state) == {"memory_context": ""}


def test_retrieve_memory_failure_degrades_to_empty(monkeypatch, graph_module):
    monkeypatch.setattr(settings, "MEMORY_V2_GRAPH", True)

    def boom(**kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(graph_module, "_search_memories", boom)
    state = {
        "messages": [HumanMessage(content="question")],
        "user_id": "u1",
        "project_id": "",
    }
    assert graph_module.retrieve_memory(state) == {"memory_context": ""}


def test_retrieve_memory_no_matches_returns_empty(monkeypatch, graph_module):
    monkeypatch.setattr(settings, "MEMORY_V2_GRAPH", True)
    monkeypatch.setattr(graph_module, "_search_memories", lambda **k: [])
    from types import SimpleNamespace

    monkeypatch.setattr(
        graph_module, "_build_embedding_provider",
        lambda: SimpleNamespace(embed=lambda texts: []),
    )
    state = {
        "messages": [HumanMessage(content="question")],
        "user_id": "u1",
        "project_id": "p1",
    }
    assert graph_module.retrieve_memory(state) == {"memory_context": ""}
