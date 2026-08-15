"""LIVE Ollama integration tests — require a running Ollama server.

These tests are NOT part of the normal hermetic suite (pytest testpaths
points at tests/ only). Run explicitly with a reachable Ollama:

    $env:OLLAMA_BASE_URL="http://localhost:11434"; python -m pytest tests_live

They verify real generation, streaming, embeddings, and dimension output
against the actual local server. Cost: none (local). Skipped unless a
reachable Ollama server is present.
"""

import os
import socket
import urllib.parse

import pytest

from app.core.config import settings
from app.core.llm_provider import build_llm
from app.services.embeddings import OllamaEmbeddingProvider

OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", settings.OLLAMA_BASE_URL)


def _reachable() -> bool:
    try:
        import httpx

        r = httpx.get(f"{OLLAMA_BASE.rstrip('/')}/api/tags", timeout=2.0)
        return r.status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _reachable(),
    reason="Ollama server not reachable — live integration tests skipped",
)


@pytest.fixture(scope="module")
def ollama_llm():
    return build_llm(model=settings.LLM_MODEL, temperature=0.0)


def test_ollama_generation(ollama_llm):
    reply = ollama_llm.invoke("Reply with exactly: OK")
    assert "OK" in reply.content


def test_ollama_streaming(ollama_llm):
    chunks = [c.content for c in ollama_llm.stream("Count from one to three.")]
    assert chunks, "expected at least one streamed chunk"
    text = "".join(chunks)
    assert text.strip()


def test_ollama_embedding_generation_and_dimension():
    p = OllamaEmbeddingProvider()
    vecs = p.embed(["hello world", "second text"])
    assert len(vecs) == 2
    assert all(len(v) == 768 for v in vecs)
    assert p.dimension == 768


def test_ollama_embedding_dimension_is_768_not_1536():
    """The 768-dim output must never be written into the vector(1536) schema."""
    p = OllamaEmbeddingProvider()
    assert p.dimension == 768
    assert p.dimension != settings.MEMORY_EMBEDDING_DIMENSION
