"""
EmbeddingProvider — config-driven abstraction for memory embeddings.

Memory V2 never hard-codes an embedding implementation. Providers:
- "openai" — OpenAI text-embedding models, batch-compatible.
- "ollama" — local Ollama embedding models (nomic-embed-text). Implemented
  and unit-tested, but produces 768-dim vectors that are INCOMPATIBLE with
  the V2.1 memory schema (vector(1536)). Do NOT set the memory provider to
  "ollama" until a dimension migration is separately decided.
- "gemini" — Google Gemini Embedding 2 API (gemini-embedding-2), 1536-dim.
  Compatible with the V2.1 memory schema. Requires GEMINI_API_KEY.
- "none"   — no provider: `get_embedding_provider()` returns None and
  retrieval/search degrades to no candidates (service layers receive
  embed=None and skip similarity work).

Dependency injection: `get_embedding_provider` is re-exported as a FastAPI
dependency in `app/api/deps.py` so endpoint tests can override it.
"""

from __future__ import annotations

import logging
from typing import Protocol

from app.core.config import settings

logger = logging.getLogger(__name__)


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


class GeminiEmbeddingProvider:
    """Google Gemini Embedding 2 provider for Memory V2 (1536-dim).

    Uses langchain_google_genai GoogleGenerativeAIEmbeddings to call the Gemini embedding API.
    Compatible with the vector(1536) memory schema column.

    Error handling:
    - Missing GEMINI_API_KEY raises ValueError at construction time.
    - API errors during embedding are raised explicitly (NOT swallowed).
      The caller is responsible for catch-and-log with fail-open semantics.
    """

    model_name: str
    dimension: int = 1536

    def __init__(self) -> None:
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            raise ValueError(
                "GeminiEmbeddingProvider requires GEMINI_API_KEY to be set. "
                "Set MEMORY_EMBEDDING_PROVIDER=none to disable memory embeddings."
            )
        model = settings.MEMORY_EMBEDDING_MODEL or "gemini-embedding-2"
        if not model.startswith("models/"):
            model = f"models/{model}"
        self.model_name = model
        self.dimension = settings.MEMORY_EMBEDDING_DIMENSION
        self._api_key = api_key

        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        self._client = GoogleGenerativeAIEmbeddings(
            google_api_key=self._api_key,
            model=self.model_name,
            output_dimensionality=self.dimension,
        )

        logger.info(
            "gemini_embedding_provider_init model=%s dimension=%d",
            self.model_name,
            self.dimension,
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts using the Gemini Embedding API.

        Raises on API errors — callers must handle and log.
        Returns an empty list for empty input.
        """
        if not texts:
            return []

        logger.debug(
            "gemini_embed_request model=%s count=%d",
            self.model_name,
            len(texts),
        )

        try:
            vecs = self._client.embed_documents(list(texts))
            results = [list(vec) for vec in vecs]
            for vec in results:
                if len(vec) != self.dimension:
                    raise ValueError(
                        f"Gemini returned {len(vec)}-dim vector; expected {self.dimension}. "
                        f"model={self.model_name}"
                    )
            logger.debug(
                "gemini_embed_complete model=%s count=%d",
                self.model_name,
                len(results),
            )
            return results
        except Exception as exc:
            logger.error(
                "gemini_embed_failed model=%s count=%d error_type=%s error=%s",
                self.model_name,
                len(texts),
                type(exc).__name__,
                exc,
            )
            raise

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query string (semantic search / retrieval use)."""
        if not text.strip():
            return []

        try:
            vec = list(self._client.embed_query(text))
            if len(vec) != self.dimension:
                raise ValueError(
                    f"Gemini returned {len(vec)}-dim query vector; expected {self.dimension}. "
                    f"model={self.model_name}"
                )
            return vec
        except Exception as exc:
            logger.error(
                "gemini_embed_query_failed model=%s error_type=%s error=%s",
                self.model_name,
                type(exc).__name__,
                exc,
            )
            raise


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

    Supported providers:
    - "openai"  — OpenAI text-embedding-3-small (1536-dim). Requires OPENAI_API_KEY.
    - "gemini"  — Gemini Embedding 2 (1536-dim). Requires GEMINI_API_KEY.
    - "ollama"  — Ollama nomic-embed-text (768-dim). NOT compatible with vector(1536).
    - "none"    — no embeddings; retrieval degrades to empty results.

    provider='ollama' is accepted (unit-tested) but is NOT compatible with
    the V2.1 vector(1536) memory schema — see OllamaEmbeddingProvider."""
    provider = settings.MEMORY_EMBEDDING_PROVIDER
    if provider == "openai":
        return OpenAIEmbeddingProvider()
    if provider == "gemini":
        return GeminiEmbeddingProvider()
    if provider == "ollama":
        return OllamaEmbeddingProvider()
    if provider == "none":
        return None
    raise ValueError(f"unknown MEMORY_EMBEDDING_PROVIDER: {provider!r}")


def build_kb_embeddings():
    """Construct the LangChain Embeddings instance for the Knowledge Base (RAG).

    Configured via KB_EMBEDDING_PROVIDER ("ollama" | "openai" | "none").
    Decouples vector_store.py from hardcoded OllamaEmbeddings construction.
    Keeps Knowledge Base embeddings strictly isolated from Memory V2 embeddings.
    """
    provider = settings.KB_EMBEDDING_PROVIDER
    if provider == "ollama":
        from langchain_ollama import OllamaEmbeddings

        return OllamaEmbeddings(
            model=settings.KB_EMBEDDING_MODEL or settings.OLLAMA_EMBEDDING_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
        )
    if provider == "openai":
        if not settings.OPENAI_API_KEY:
            raise ValueError(
                "KB_EMBEDDING_PROVIDER=openai requires OPENAI_API_KEY to be set. "
                "Refusing to construct the OpenAI Embeddings client without credentials."
            )
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(
            model=settings.KB_EMBEDDING_MODEL or "text-embedding-3-small",
            api_key=settings.OPENAI_API_KEY,
        )
    if provider == "none":
        return None
    raise ValueError(f"unknown KB_EMBEDDING_PROVIDER: {provider!r}")