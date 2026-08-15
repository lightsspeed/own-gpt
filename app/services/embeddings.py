"""
EmbeddingProvider — config-driven abstraction for memory embeddings.

Memory V2 never hard-codes an embedding implementation. Providers:
- "openai" — OpenAI text-embedding models, batch-compatible.
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


def build_embedding_provider() -> EmbeddingProvider | None:
    """Resolve the configured provider; None for provider='none'."""
    provider = settings.MEMORY_EMBEDDING_PROVIDER
    if provider == "openai":
        return OpenAIEmbeddingProvider()
    if provider == "none":
        return None
    raise ValueError(f"unknown MEMORY_EMBEDDING_PROVIDER: {provider!r}")