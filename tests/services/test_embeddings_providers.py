"""Hermetic unit tests for embedding provider selection (app/services/embeddings.py).

Covers the OpenAI provider, the Ollama provider (implemented but disabled
for V2.1 memory), provider switching, and the vector(1536) compatibility
contract. No network calls: langchain clients are faked.
"""

import pytest

from app.core.config import settings
from app.services.embeddings import (
    GeminiEmbeddingProvider,
    OpenAIEmbeddingProvider,
    OllamaEmbeddingProvider,
    build_embedding_provider,
    build_kb_embeddings,
)


def _set(monkeypatch, **kwargs):
    for k, v in kwargs.items():
        monkeypatch.setattr(settings, k, v)


@pytest.fixture
def fake_ollama_client(monkeypatch):
    import sys

    calls = {"dim": 768}

    class FakeOllamaEmbeddings:
        def __init__(self, **kwargs):
            calls["kwargs"] = kwargs

        def embed_documents(self, texts):
            return [[0.1] * calls["dim"] for _ in texts]

    monkeypatch.setitem(sys.modules, "langchain_ollama", type("M", (), {
        "OllamaEmbeddings": FakeOllamaEmbeddings,
    })())
    return calls


@pytest.fixture
def fake_openai_client(monkeypatch):
    import sys

    calls = {"dim": 1536}

    class FakeOpenAIEmbeddings:
        def __init__(self, **kwargs):
            calls["kwargs"] = kwargs

        def embed_documents(self, texts):
            return [[0.2] * calls["dim"] for _ in texts]

    monkeypatch.setitem(sys.modules, "langchain_openai", type("M", (), {
        "OpenAIEmbeddings": FakeOpenAIEmbeddings,
    })())
    return calls


class TestOllamaEmbeddingProvider:
    def test_dimension_is_768(self, fake_ollama_client):
        _set(monkeypatch=fake_ollama_client, )
        p = OllamaEmbeddingProvider()
        assert p.dimension == 768

    def test_model_and_base_url_passed_to_client(self, monkeypatch, fake_ollama_client):
        _set(
            monkeypatch,
            OLLAMA_EMBEDDING_MODEL="nomic-embed-text",
            OLLAMA_BASE_URL="http://ollama:11434",
        )
        OllamaEmbeddingProvider()
        assert fake_ollama_client["kwargs"]["model"] == "nomic-embed-text"
        assert fake_ollama_client["kwargs"]["base_url"] == "http://ollama:11434"

    def test_embed_batch_shape(self, monkeypatch, fake_ollama_client):
        _set(monkeypatch, OLLAMA_EMBEDDING_MODEL="nomic-embed-text")
        p = OllamaEmbeddingProvider()
        vecs = p.embed(["hello", "world"])
        assert len(vecs) == 2
        assert all(len(v) == 768 for v in vecs)

    def test_embed_empty_is_noop(self, monkeypatch, fake_ollama_client):
        p = OllamaEmbeddingProvider()
        assert p.embed([]) == []


@pytest.fixture
def fake_gemini_client(monkeypatch):
    import sys

    calls = {"dim": 1536}

    class FakeGoogleGenerativeAIEmbeddings:
        def __init__(self, **kwargs):
            calls["kwargs"] = kwargs

        def embed_documents(self, texts):
            return [[0.3] * calls["dim"] for _ in texts]

        def embed_query(self, text):
            return [0.3] * calls["dim"]

    monkeypatch.setitem(sys.modules, "langchain_google_genai", type("M", (), {
        "GoogleGenerativeAIEmbeddings": FakeGoogleGenerativeAIEmbeddings,
    })())
    return calls


class TestGeminiEmbeddingProvider:
    def test_gemini_provider_init(self, monkeypatch, fake_gemini_client):
        _set(monkeypatch, GEMINI_API_KEY="test-gemini-key", MEMORY_EMBEDDING_MODEL="gemini-embedding-2", MEMORY_EMBEDDING_DIMENSION=1536)
        p = GeminiEmbeddingProvider()
        assert p.dimension == 1536
        assert p.model_name == "models/gemini-embedding-2"
        assert fake_gemini_client["kwargs"]["google_api_key"] == "test-gemini-key"

    def test_gemini_missing_api_key_raises(self, monkeypatch):
        _set(monkeypatch, GEMINI_API_KEY="", MEMORY_EMBEDDING_PROVIDER="gemini")
        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            GeminiEmbeddingProvider()

    def test_gemini_embed_documents_batch(self, monkeypatch, fake_gemini_client):
        _set(monkeypatch, GEMINI_API_KEY="test-key", MEMORY_EMBEDDING_DIMENSION=1536)
        p = GeminiEmbeddingProvider()
        vecs = p.embed(["fact 1", "fact 2"])
        assert len(vecs) == 2
        assert len(vecs[0]) == 1536
        assert len(vecs[1]) == 1536

    def test_gemini_embed_query_single(self, monkeypatch, fake_gemini_client):
        _set(monkeypatch, GEMINI_API_KEY="test-key", MEMORY_EMBEDDING_DIMENSION=1536)
        p = GeminiEmbeddingProvider()
        vec = p.embed_query("what is my favorite color?")
        assert len(vec) == 1536

    def test_gemini_dimension_1536(self, monkeypatch, fake_gemini_client):
        _set(monkeypatch, GEMINI_API_KEY="test-key", MEMORY_EMBEDDING_DIMENSION=1536)
        p = GeminiEmbeddingProvider()
        assert p.dimension == 1536


class TestProviderSelection:
    def test_openai_selected_by_default_contract(self, monkeypatch, fake_openai_client):
        _set(monkeypatch, MEMORY_EMBEDDING_PROVIDER="openai", MEMORY_EMBEDDING_DIMENSION=1536)
        p = build_embedding_provider()
        assert isinstance(p, OpenAIEmbeddingProvider)
        assert p.dimension == 1536

    def test_gemini_selected(self, monkeypatch, fake_gemini_client):
        _set(monkeypatch, MEMORY_EMBEDDING_PROVIDER="gemini", GEMINI_API_KEY="test-key", MEMORY_EMBEDDING_DIMENSION=1536)
        p = build_embedding_provider()
        assert isinstance(p, GeminiEmbeddingProvider)
        assert p.dimension == 1536

    def test_openai_dimension_matches_vector_schema(self, monkeypatch, fake_openai_client):
        # V2.1 schema contract: memory embeddings must stay vector(1536)-compatible.
        _set(monkeypatch, MEMORY_EMBEDDING_PROVIDER="openai", MEMORY_EMBEDDING_DIMENSION=1536)
        p = build_embedding_provider()
        assert p.dimension == 1536 == settings.MEMORY_EMBEDDING_DIMENSION
        assert len(p.embed(["x"])[0]) == 1536

    def test_ollama_selectable_via_factory(self, monkeypatch, fake_ollama_client):
        _set(monkeypatch, MEMORY_EMBEDDING_PROVIDER="ollama", MEMORY_EMBEDDING_MODEL="nomic-embed-text")
        p = build_embedding_provider()
        assert isinstance(p, OllamaEmbeddingProvider)
        assert p.dimension == 768

    def test_none_returns_none(self, monkeypatch, fake_openai_client, fake_ollama_client):
        _set(monkeypatch, MEMORY_EMBEDDING_PROVIDER="none")
        assert build_embedding_provider() is None

    def test_unknown_provider_raises(self, monkeypatch):
        _set(monkeypatch, MEMORY_EMBEDDING_PROVIDER="anthropic")
        with pytest.raises(ValueError, match="anthropic"):
            build_embedding_provider()


class TestMemoryProviderUnchanged:
    def test_default_memory_provider_valid(self):
        # The V2.1 memory configuration must point at a 1536-dim provider:
        # the schema column is vector(1536) and dimension migration is out of scope.
        assert settings.MEMORY_EMBEDDING_PROVIDER in ("gemini", "openai", "none")
        assert settings.MEMORY_EMBEDDING_DIMENSION == 1536

    def test_ollama_provider_never_silently_used_for_memory(self, monkeypatch, fake_openai_client):
        # Even with an Ollama-capable environment, memory construction resolves
        # exactly what the configuration says — no hidden switching.
        _set(monkeypatch, MEMORY_EMBEDDING_PROVIDER="openai", MEMORY_EMBEDDING_DIMENSION=1536)
        p = build_embedding_provider()
        assert isinstance(p, OpenAIEmbeddingProvider)


class TestKBEmbeddingProvider:
    def test_kb_ollama_selected_by_default(self, monkeypatch, fake_ollama_client):
        _set(monkeypatch, KB_EMBEDDING_PROVIDER="ollama", KB_EMBEDDING_MODEL="nomic-embed-text")
        embedder = build_kb_embeddings()
        assert fake_ollama_client["kwargs"]["model"] == "nomic-embed-text"

    def test_kb_openai_selected(self, monkeypatch, fake_openai_client):
        _set(monkeypatch, KB_EMBEDDING_PROVIDER="openai", KB_EMBEDDING_MODEL="text-embedding-3-small", OPENAI_API_KEY="test-key")
        embedder = build_kb_embeddings()
        assert fake_openai_client["kwargs"]["model"] == "text-embedding-3-small"

    def test_kb_openai_requires_api_key(self, monkeypatch, fake_openai_client):
        _set(monkeypatch, KB_EMBEDDING_PROVIDER="openai", OPENAI_API_KEY="")
        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            build_kb_embeddings()

    def test_kb_none_returns_none(self, monkeypatch):
        _set(monkeypatch, KB_EMBEDDING_PROVIDER="none")
        assert build_kb_embeddings() is None

    def test_kb_unsupported_provider_raises(self, monkeypatch):
        _set(monkeypatch, KB_EMBEDDING_PROVIDER="invalid_provider")
        with pytest.raises(ValueError, match="invalid_provider"):
            build_kb_embeddings()


