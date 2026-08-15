"""
LLMProvider — config-driven factory for chat models.

The application depends on this boundary, never on a concrete provider:
- "ollama" — local Ollama server (ChatOllama), default for local development.
- "openai" — OpenAI chat models (ChatOpenAI), requires OPENAI_API_KEY.

Invariants:
- There is NO automatic fallback between providers. The configured provider
  is the only one ever constructed; if it is unreachable or misconfigured,
  the failure is raised clearly at construction/request time.
- provider=ollama never reads OPENAI_API_KEY; provider=openai without a key
  fails at construction with a clear error.
- max_tokens maps to the provider-native equivalent (num_predict for Ollama),
  so callers express capability needs, not provider details.

Call sites (agent graph, chat title, intent/rewrite/validation pipeline,
episodic summarization, memory extraction) all route through build_llm.
"""

from __future__ import annotations

import logging

from langchain_core.language_models import BaseChatModel

from app.core.config import settings
from app.core.model_config import DEFAULT_MODEL

logger = logging.getLogger(__name__)


class LLMProviderError(ValueError):
    """Raised when the configured LLM provider is invalid or unusable."""


def _build_openai(
    model: str | None, temperature: float, max_tokens: int | None
) -> BaseChatModel:
    if not settings.OPENAI_API_KEY:
        raise LLMProviderError(
            "LLM_PROVIDER=openai requires OPENAI_API_KEY to be set. "
            "Refusing to construct the OpenAI client without credentials."
        )
    from langchain_openai import ChatOpenAI  # deferred — heavy import

    kwargs: dict = {
        "model": model or DEFAULT_MODEL,
        "temperature": temperature,
        "api_key": settings.OPENAI_API_KEY,
    }
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    return ChatOpenAI(**kwargs)


def _build_ollama(
    model: str | None, temperature: float, max_tokens: int | None
) -> BaseChatModel:
    from langchain_ollama import ChatOllama  # deferred — heavy import

    kwargs: dict = {
        "model": model or settings.LLM_MODEL,
        "temperature": temperature,
        "base_url": settings.OLLAMA_BASE_URL,
    }
    if max_tokens is not None:
        # Ollama's native token budget parameter (OpenAI's max_tokens).
        kwargs["num_predict"] = max_tokens
    return ChatOllama(**kwargs)


def build_llm(
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> BaseChatModel:
    """Construct the chat model for the configured provider.

    model: provider-native model name; None resolves the provider default
    (OLLAMA LLM_MODEL / OpenAI DEFAULT_MODEL).
    temperature: clamped by the API layer before reaching the agent graph;
    internal call sites pass their own values (0.0 for deterministic steps).
    """
    temp = temperature if temperature is not None else settings.TEMPERATURE_DEFAULT
    provider = settings.LLM_PROVIDER
    if provider == "openai":
        return _build_openai(model, temp, max_tokens)
    if provider == "ollama":
        return _build_ollama(model, temp, max_tokens)
    raise LLMProviderError(
        f"unknown LLM_PROVIDER: {provider!r} (supported: 'openai', 'ollama')"
    )
