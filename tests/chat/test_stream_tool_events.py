"""Focused SSE contract tests for /chat/stream.

Covers the tool event vocabulary (tool_start / tool_end) and the citation
resources round trip (SSE resources → persisted assistant message → history).
"""

import json
from dataclasses import dataclass, field
from typing import Optional

from langchain_core.messages import ToolMessage

from tests.chat.conftest import FakeEvidenceBuilder, FakePipeline


@dataclass
class FakeEvidence:
    source_type: str
    title: str
    url: Optional[str]
    chunk: str
    document_id: Optional[str]
    chunk_index: Optional[int]
    page: Optional[int]
    section: Optional[str]
    confidence_label: object = None

    def model_dump(self, exclude=None):
        return {
            "source_type": self.source_type,
            "title": self.title,
            "url": self.url,
            "chunk": self.chunk,
            "document_id": self.document_id,
            "chunk_index": self.chunk_index,
            "page": self.page,
            "section": self.section,
            "confidence_label": getattr(self.confidence_label, "value", None),
        }


class StubEvidenceBuilder(FakeEvidenceBuilder):
    def __init__(self, items):
        self._items = items

    def build(self, **kwargs):
        return type("R", (), {"evidence": self._items})()


def _sse_events(resp):
    data = resp.text
    events = []
    for block in data.split("\n\n"):
        block = block.strip()
        if not block.startswith("data: "):
            continue
        payload = block[len("data: "):].strip()
        if payload == "[DONE]":
            events.append({"type": "[DONE]"})
            continue
        events.append(json.loads(payload))
    return events


def _stream_request(client, alice_token, session_id="sess-1", **body_kwargs):
    body = {
        "session_id": session_id,
        "message": "hello",
        "project_id": None,
        "active_tools": {"web": True, "kb": True},
    }
    body.update(body_kwargs)
    return client.post(
        "/chat/stream",
        json=body,
        headers={"Authorization": f"Bearer {alice_token}"},
    )


def test_tool_end_emitted_from_action_node(client, chat_module, fake_graph, alice_token):
    """tool_start + tool_end are emitted for a real tool round trip.

    The graph has an `action` node (not `tools`); ToolMessages carry the
    tool name. Both must reach the client as SSE events.
    """
    fake_graph.partial_chunks = ["answer"]
    fake_graph.agent_tool_calls = [{
        "name": "web_search", "args": {"query": "x"}, "id": "call-1", "type": "tool_call",
    }]
    fake_graph.action_tool_messages = [
        ToolMessage(content="[tool:web_search] ok", tool_call_id="call-1", name="web_search")
    ]

    resp = _stream_request(client, alice_token)
    assert resp.status_code == 200
    events = _sse_events(resp)
    types = [e["type"] for e in events]

    assert "tool_start" in types
    assert "tool_end" in types
    start = next(e for e in events if e["type"] == "tool_start")
    end = next(e for e in events if e["type"] == "tool_end")
    assert start["tool"] == "web_search"
    assert end["tool"] == "web_search"


def test_tool_end_emitted_for_kb_tool(client, chat_module, fake_graph, alice_token):
    fake_graph.partial_chunks = ["answer"]
    fake_graph.agent_tool_calls = [{
        "name": "search_knowledge_base", "args": {"query": "x"}, "id": "call-2", "type": "tool_call",
    }]
    fake_graph.action_tool_messages = [
        ToolMessage(content="[tool:search_knowledge_base] ok", tool_call_id="call-2", name="search_knowledge_base")
    ]

    resp = _stream_request(client, alice_token)
    assert resp.status_code == 200
    events = _sse_events(resp)
    ends = [e for e in events if e["type"] == "tool_end"]
    assert ends and ends[0]["tool"] == "search_knowledge_base"


def test_no_tool_events_without_tool_calls(client, chat_module, fake_graph, alice_token):
    fake_graph.partial_chunks = ["plain answer"]
    resp = _stream_request(client, alice_token)
    assert resp.status_code == 200
    types = [e["type"] for e in _sse_events(resp)]
    assert "tool_start" not in types
    assert "tool_end" not in types


def test_history_keeps_resources_from_stream(client, chat_module, fake_graph, alice_token):
    """SSE resources are persisted so history reload keeps citations."""
    item = FakeEvidence(
        source_type="knowledge",
        title="guide.pdf",
        url=None,
        chunk="chunk text",
        document_id="guide.pdf",
        chunk_index=3,
        page=2,
        section="Intro",
    )
    chat_module._pipeline._evidence_builder = StubEvidenceBuilder([item])
    fake_graph.partial_chunks = ["grounded answer"]

    resp = _stream_request(client, alice_token)
    assert resp.status_code == 200
    events = _sse_events(resp)
    resources_event = next(e for e in events if e["type"] == "resources")
    assert resources_event["resources"][0]["title"] == "guide.pdf"

    hist = client.get(
        "/chat/sess-1/history",
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    assert hist.status_code == 200
    messages = hist.json()["messages"]
    assistant = [m for m in messages if m["role"] == "assistant"]
    assert len(assistant) == 1
    assert assistant[0]["resources"] == [
        {
            "type": "file",
            "title": "guide.pdf",
            "url": None,
            "snippet": "chunk text",
            "document_id": "guide.pdf",
            "chunk_index": 3,
            "page": 2,
            "section": "Intro",
            "confidence_label": None,
        }
    ]


def test_stream_captures_agent_usage_and_finalizes_trace_once(
    client, chat_module, fake_graph, alice_token, monkeypatch
):
    """The stream path feeds agent LLM usage back + closes the trace once.

    Mirrors the production wiring: the agent node update carries
    usage_metadata (the real graph returns the raw provider response), the
    API layer records it into the shared budget, and finalize_trace emits
    the single request_completed after the graph finished.
    """
    recorded = {"finalize": 0, "usage": []}

    class RecorderPipeline(FakePipeline):
        def record_agent_usage(self, ctx, usage_metadata=None, *, fallback_model=""):
            if isinstance(usage_metadata, dict) and usage_metadata:
                recorded["usage"].append(dict(usage_metadata))

        def finalize_trace(self, ctx, status=None):
            recorded["finalize"] += 1

    monkeypatch.setattr(chat_module, "_pipeline", RecorderPipeline())
    fake_graph.partial_chunks = ["answer"]
    fake_graph.agent_usage_metadata = {
        "input_tokens": 10, "completion_tokens": 5, "model": "gpt-4o-mini",
    }

    resp = _stream_request(client, alice_token)
    assert resp.status_code == 200
    assert "data: [DONE]" in resp.text

    assert recorded["usage"] == [
        {"input_tokens": 10, "completion_tokens": 5, "model": "gpt-4o-mini"}
    ]
    assert recorded["finalize"] == 1