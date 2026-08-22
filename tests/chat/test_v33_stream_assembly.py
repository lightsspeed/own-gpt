"""Phase 3.3 — SSE streaming assembly integrity tests.

Exercises the REAL app.api.endpoints.chat stream path with Gemini-3 style
list-content chunks (AIMessageChunk.content = [{"type": "text", "text": ..}]),
which is the exact shape that previously lost leading whitespace through
_flatten_content and glued headings, words, and YAML lines together.

Proves the root-cause fix: provider deltas are concatenated byte-for-byte,
and the final assembled response passes through the deterministic
normalize_markdown layer before persistence.
"""

import json

from app.agent.pipeline.markdown_integrity import normalize_markdown

from tests.chat.test_stream_tool_events import _stream_request, _sse_events


def _list_chunk(text: str):
    return [{"type": "text", "text": text}]


def _content_payloads(resp):
    events = _sse_events(resp)
    chunks = "".join(e["content"] for e in events if e["type"] == "content")
    return events, chunks


def _assistant_history(client, alice_token, session_id="sess-1"):
    hist = client.get(
        f"/chat/{session_id}/history",
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    assert hist.status_code == 200
    messages = hist.json()["messages"]
    return [m for m in messages if m["role"] == "assistant"]


def test_stream_preserves_chunk_whitespace_and_structure(
    client, chat_module, fake_graph, alice_token
):
    """The documented production defects no longer reproduce.

    Tokens carry the normal leading/trailing whitespace that Gemini-3 emits
    at chunk boundaries; the OLD code stripped it, producing the glued text
    seen in production (`### ...?In Kubernetes,`, word glue, YAML newline
    loss). The fixed assembly must preserve it end-to-end.
    """
    fake_graph.partial_chunks = [
        _list_chunk("### What is a Kubernetes Service?"),
        _list_chunk("\n\nIn Kubernetes, a Service is an"),
        _list_chunk(" abstraction that defines a logical"),
        _list_chunk("\nset of pods.\n\n"),
        _list_chunk("- **Labels and Selectors**\n"),
        _list_chunk("- **Endpoints / EndpointSlices**\n"),
        _list_chunk("- **Kube-Proxy**\n\n"),
        _list_chunk("```yaml\napiVersion: v1\nkind: Service\n```\n\n"),
        _list_chunk("necessary.---### Core Concepts\n"),
    ]

    resp = _stream_request(client, alice_token)
    assert resp.status_code == 200
    events, joined = _content_payloads(resp)

    # Whitespace boundaries survive the stream path (raw SSE content).
    assert "What is a Kubernetes Service?\n\nIn Kubernetes," in joined
    assert "a Service is an abstraction" in joined
    assert "logical\nset of pods." in joined
    assert "Labels and Selectors" in joined
    assert "```yaml\napiVersion: v1\nkind: Service\n```" in joined

    # The streamed raw text is preserved faithfully (no per-chunk munge)…
    assert "necessary.---### Core Concepts" in joined

    # …and the deterministic layer repairs the structural glue at finalize.
    assistants = _assistant_history(client, alice_token)
    assert len(assistants) == 1
    persisted = assistants[0]["content"]
    assert "necessary.\n\n---\n\n### Core Concepts" in persisted
    assert persisted == normalize_markdown(joined.strip())


def test_stream_fixes_heading_split_across_chunks(client, chat_module, fake_graph, alice_token):
    """A heading marker split across chunk boundaries assembles correctly."""
    fake_graph.partial_chunks = [
        _list_chunk("Core concepts:"),
        _list_chunk("#### 1. "),
        _list_chunk("ServiceAccounts\n"),
    ]

    resp = _stream_request(client, alice_token)
    assert resp.status_code == 200
    _, joined = _content_payloads(resp)

    # Streamed raw text is preserved faithfully (glue only appears in the
    # already-broken input)…
    assert "Core concepts:#### 1. ServiceAccounts" in joined

    # …and the deterministic layer separates the heading at finalize.
    assistants = _assistant_history(client, alice_token)
    assert len(assistants) == 1
    assert "Core concepts:\n\n#### 1. ServiceAccounts" in assistants[0]["content"]


def test_stream_keeps_whitespace_only_and_space_lead_chunks(
    client, chat_module, fake_graph, alice_token
):
    """Whitespace-only / pure-delimiter deltas are no longer dropped."""
    fake_graph.partial_chunks = [
        _list_chunk("Kubernetes automatically"),
        _list_chunk(" "),
        _list_chunk("schedules pods"),
        _list_chunk("\n"),
        _list_chunk("with a consistent policy."),
    ]

    resp = _stream_request(client, alice_token)
    assert resp.status_code == 200
    _, joined = _content_payloads(resp)

    assert "Kubernetes automatically schedules pods" in joined
    assert "\nwith a consistent policy." in joined


def test_stream_list_chunk_image_placeholder(client, chat_module, fake_graph, alice_token):
    """Non-text blocks still flatten without whitespace corruption."""
    fake_graph.partial_chunks = [
        _list_chunk("Here is a diagram:\n\n[Image]"),
        _list_chunk("\nCaption below."),
    ]

    resp = _stream_request(client, alice_token)
    assert resp.status_code == 200
    _, joined = _content_payloads(resp)

    assert "Here is a diagram:\n\n[Image]\nCaption below." in joined