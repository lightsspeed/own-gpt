"""
EmbeddingProvider — config-driven abstraction for memory embeddings.

Memory V2 never hard-codes an embedding implementation. Providers:
- "openai" — OpenAI text-embedding models, batch-compatible.
- "ollama" — local Ollama embedding models (nomic-embed-text). Implemented
  and unit-tested, but produces 768-dim vectors that are INCOMPATIBLE with
  the V2.1 memory schema (vector(1536)). Do NOT set the memory provider to
  "ollama" until a dimension migration is separately decided.
- "none"   — no provider: `get_embedding_provider()` returns None and
  retrieval/search degrades to no candidates (service layers receive
  embed=None and skip similarity work).

Dependency injection: `get_embedding_provider` is re-exported as a FastAPI
dependency in `app/api/deps.py` so endpoint tests can override it.
"""

from __future__ import annotations

from typing import Protocol

from app.core.config import settings


class EmbeddingProvider(Protocol):
    """Batch embedder contract for memory V2."""

    model_name: str
    dimension: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class OpenAIEmbeddingProvider:
    """Binding to langchain_openai. Lazy-imported so the memory service and
    tests never require the package when provider='none'."""

    model_name: str
    dimension: int

    def __init__(self) -> None:
        from langchain_openai import OpenAIEmbeddings

        self.model_name = settings.MEMORY_EMBEDDING_MODEL
        self.dimension = settings.MEMORY_EMBEDDING_DIMENSION
        self._client = OpenAIEmbeddings(
            model=self.model_name,
            dimensions=self.dimension,
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return [list(vec) for vec in self._client.embed_documents(list(texts))]


class OllamaEmbeddingProvider:
    """Binding to langchain_ollama (nomic-embed-text, 768-dim).

    IMPORTANT: the 768-dim output is incompatible with the V2.1 memory schema
    (vector(1536)). This provider exists behind the abstraction for future
    use and is unit-tested, but must NOT be configured as the memory provider
    (MEMORY_EMBEDDING_PROVIDER) until a dimension migration is decided.
    """

    model_name: str
    dimension: int = 768

    def __init__(self) -> None:
        from langchain_ollama import OllamaEmbeddings

        self.model_name = settings.OLLAMA_EMBEDDING_MODEL
        self._client = OllamaEmbeddings(
            model=self.model_name,
            base_url=settings.OLLAMA_BASE_URL,
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return [list(vec) for vec in self._client.embed_documents(list(texts))]


def build_embedding_provider() -> EmbeddingProvider | None:
    """Resolve the configured provider; None for provider='none'.

    provider='ollama' is accepted (unit-tested) but is NOT compatible with
    the V2.1 vector(1536) memory schema — see OllamaEmbeddingProvider."""
    provider = settings.MEMORY_EMBEDDING_PROVIDER
    if provider == "openai":
        return OpenAIEmbeddingProvider()
    if provider == "ollama":
        return OllamaEmbeddingProvider()
    if provider == "none":
        return None
    raise ValueError(f"unknown MEMORY_EMBEDDING_PROVIDER: {provider!r}")