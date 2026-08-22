"""
LLMProvider — config-driven factory for chat models.

The application depends on this boundary, never on a concrete provider:
- "ollama"  — local Ollama server (ChatOllama), default for local development.
- "openai"  — OpenAI chat models (ChatOpenAI), requires OPENAI_API_KEY.
- "groq"    — Groq cloud inference (ChatOpenAI against the OpenAI-compatible
              Groq base URL), requires GROQ_API_KEY.
- "gemini"  — Google Gemini via langchain-google-genai (ChatGoogleGenerativeAI),
              requires GEMINI_API_KEY. Supports streaming and tool-calling.

Invariants:
- There is NO automatic fallback between providers. The configured provider
  is the only one ever constructed; if it is unreachable or misconfigured,
  the failure is raised clearly at construction/request time.
- provider=ollama never reads OPENAI_API_KEY; provider=openai without a key
  fails at construction with a clear error. Same for provider=groq/GROQ_API_KEY
  and provider=gemini/GEMINI_API_KEY.
- max_tokens maps to the provider-native equivalent (num_predict for Ollama,
  max_tokens for OpenAI-compatible and Gemini endpoints), so callers express
  capability needs, not provider details.

Call sites (agent graph, chat title, intent/rewrite/validation pipeline,
episodic summarization, memory extraction) all route through build_llm.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from langchain_core.language_models import BaseChatModel

from app.core.config import settings
from app.core.model_config import DEFAULT_MODEL

logger = logging.getLogger(__name__)


class LLMProviderError(ValueError):
    """Raised when the configured LLM provider is invalid or unusable."""


# ---------------------------------------------------------------------------
# Provider-neutral error taxonomy.
#
# Provider-specific exceptions are mapped to these stable categories at this
# boundary. Clients receive the category CODE and a safe, human-readable
# message — never raw provider exception text.
# ---------------------------------------------------------------------------

PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
MODEL_GENERATION_FAILED = "MODEL_GENERATION_FAILED"
TOOL_CALL_FAILED = "TOOL_CALL_FAILED"
STRUCTURED_OUTPUT_FAILED = "STRUCTURED_OUTPUT_FAILED"
RETRIEVAL_FAILED = "RETRIEVAL_FAILED"
EMBEDDING_PROVIDER_FAILED = "EMBEDDING_PROVIDER_FAILED"
APPLICATION_ERROR = "APPLICATION_ERROR"

SAFE_ERROR_MESSAGES: dict[str, str] = {
    PROVIDER_UNAVAILABLE: "The AI provider is temporarily unavailable. Please try again.",
    MODEL_GENERATION_FAILED: "The model could not generate a response. Please try again.",
    TOOL_CALL_FAILED: "The model could not complete the requested tool operation. Please try again.",
    STRUCTURED_OUTPUT_FAILED: "The model returned an invalid structured response. Please try again.",
    RETRIEVAL_FAILED: "Knowledge retrieval failed. Please try again.",
    EMBEDDING_PROVIDER_FAILED: "The embedding service is unavailable. Please try again.",
    APPLICATION_ERROR: "An internal error occurred.",
}

# Errors mapped to these codes are safe to retry ONCE at the model-invocation
# boundary (transient provider state, intermittent tool-call emission). All
# other codes are never retried — including MODEL_GENERATION_FAILED, which
# covers deterministic rejections (unknown model, content policy).
RETRYABLE_CODES: frozenset[str] = frozenset({PROVIDER_UNAVAILABLE, TOOL_CALL_FAILED})


@dataclass(frozen=True)
class ProviderErrorInfo:
    """Provider-neutral classification of an LLM/provider failure."""

    code: str
    retryable: bool
    safe_message: str


def _error_text(exc: Exception) -> str:
    """Best-effort flattened error text for matching; never sent to clients."""
    parts: list[str] = []
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            parts.append(str(err.get("code", "")))
            parts.append(str(err.get("message", "")))
    parts.append(str(getattr(exc, "message", exc)))
    return " ".join(p for p in parts if p)


def _info(code: str, retryable: bool | None = None) -> ProviderErrorInfo:
    # retryable defaults to the code-level policy; callers may override for
    # sub-cases that must never be retried (auth/config failures).
    return ProviderErrorInfo(
        code=code,
        retryable=code in RETRYABLE_CODES if retryable is None else retryable,
        safe_message=SAFE_ERROR_MESSAGES[code],
    )


def classify_provider_error(exc: Exception, provider: str | None = None) -> ProviderErrorInfo:
    """Map a provider/application exception to the provider-neutral taxonomy.

    provider: explicit overrides (defaults to the configured LLM_PROVIDER).
    Never raises and never includes raw provider text in the safe message.
    """
    if isinstance(exc, LLMProviderError):
        # Configuration issue: never retried.
        return _info(PROVIDER_UNAVAILABLE, retryable=False)

    try:
        import openai as _openai  # deferred — heavy import

        if isinstance(exc, (_openai.AuthenticationError, _openai.PermissionDeniedError)):
            return _info(PROVIDER_UNAVAILABLE, retryable=False)
        if isinstance(exc, _openai.RateLimitError):
            return _info(PROVIDER_UNAVAILABLE)
        if isinstance(exc, (_openai.APIConnectionError, _openai.APITimeoutError)):
            return _info(PROVIDER_UNAVAILABLE)
        if isinstance(exc, _openai.InternalServerError):
            return _info(PROVIDER_UNAVAILABLE)
        if isinstance(exc, _openai.NotFoundError):
            return _info(MODEL_GENERATION_FAILED)
        if isinstance(exc, _openai.BadRequestError):
            text = _error_text(exc)
            if "tool_use_failed" in text or "failed_generation" in text:
                return _info(TOOL_CALL_FAILED)  # intermittent model-side tool emission
            if "response_format" in text or "json" in text.lower():
                return _info(STRUCTURED_OUTPUT_FAILED)
            return _info(MODEL_GENERATION_FAILED)
    except ImportError:
        pass

    try:
        import ollama as _ollama  # deferred — heavy import

        if isinstance(exc, _ollama.ResponseError):
            status = getattr(exc, "status_code", 0)
            text = f"{getattr(exc, 'error', '')} {getattr(exc, 'message', '')}".lower()
            if status in (400, 422) and ("tool" in text or "function" in text):
                return _info(TOOL_CALL_FAILED)
            if status in (429, 500, 502, 503, 504):
                return _info(PROVIDER_UNAVAILABLE)
            if status in (401, 403):
                return _info(PROVIDER_UNAVAILABLE)
            if status == 404:
                return _info(MODEL_GENERATION_FAILED)
            return _info(MODEL_GENERATION_FAILED)
    except ImportError:
        pass

    try:
        import httpx as _httpx

        if isinstance(exc, _httpx.HTTPError):
            return _info(PROVIDER_UNAVAILABLE)  # transport-level (timeouts, connect)
    except ImportError:
        pass

    try:
        import requests as _requests

        if isinstance(exc, _requests.RequestException):
            return _info(PROVIDER_UNAVAILABLE)
    except ImportError:
        pass

    try:
        import google.api_core.exceptions as _gexc  # deferred — google-genai

        if isinstance(exc, _gexc.Unauthenticated):
            return _info(PROVIDER_UNAVAILABLE, retryable=False)
        if isinstance(exc, _gexc.PermissionDenied):
            return _info(PROVIDER_UNAVAILABLE, retryable=False)
        if isinstance(exc, _gexc.ResourceExhausted):
            return _info(PROVIDER_UNAVAILABLE)  # quota / rate limit, retryable
        if isinstance(exc, (_gexc.ServiceUnavailable, _gexc.DeadlineExceeded)):
            return _info(PROVIDER_UNAVAILABLE)
        if isinstance(exc, _gexc.InvalidArgument):
            # Covers malformed tool-call payloads from the model side.
            text = _error_text(exc)
            if "tool" in text.lower() or "function" in text.lower():
                return _info(TOOL_CALL_FAILED)
            return _info(MODEL_GENERATION_FAILED, retryable=False)
        if isinstance(exc, _gexc.NotFound):
            return _info(MODEL_GENERATION_FAILED, retryable=False)
        if isinstance(exc, _gexc.GoogleAPICallError):
            # Catch-all for any other google API call failures.
            return _info(PROVIDER_UNAVAILABLE)
    except ImportError:
        pass

    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        return _info(PROVIDER_UNAVAILABLE)
    return _info(APPLICATION_ERROR)


def invoke_model_with_retry(model: BaseChatModel, payload, provider: str | None = None):
    """Invoke a chat model with AT MOST ONE retry for retryable failures.

    Retry policy:
    - Maximum 2 attempts total; a retryable failure triggers exactly one retry.
    - Only exceptions classified retryable (PROVIDER_UNAVAILABLE /
      TOOL_CALL_FAILED / MODEL_GENERATION_FAILED) are retried.
    - Retries reuse the SAME model instance — there is never a fallback to
      another provider.
    - A successful response is never retried: an AIMessage carrying tool_calls
      is a successful generation; tools execute later in the action node, and
      side effects must never run twice.
    """
    provider = provider or settings.LLM_PROVIDER
    try:
        return model.invoke(payload)
    except Exception as first_exc:
        info = classify_provider_error(first_exc, provider)
        if not info.retryable:
            raise
        logger.warning(
            "provider_retry provider=%s code=%s attempt=1/2 error=%s",
            provider,
            info.code,
            first_exc,
        )
        try:
            return model.invoke(payload)
        except Exception as second_exc:
            logger.error(
                "provider_retry_failed provider=%s code=%s attempts=2 error=%s",
                provider,
                info.code,
                second_exc,
            )
            raise


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


def _build_groq(
    model: str | None, temperature: float, max_tokens: int | None
) -> BaseChatModel:
    if not settings.GROQ_API_KEY:
        raise LLMProviderError(
            "LLM_PROVIDER=groq requires GROQ_API_KEY to be set. "
            "Refusing to construct the Groq client without credentials."
        )
    from langchain_openai import ChatOpenAI  # deferred — heavy import

    kwargs: dict = {
        "model": model or settings.GROQ_MODEL,
        "temperature": temperature,
        "api_key": settings.GROQ_API_KEY,
        "base_url": settings.GROQ_BASE_URL,
    }
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    return ChatOpenAI(**kwargs)


def _build_gemini(
    model: str | None, temperature: float, max_tokens: int | None
) -> BaseChatModel:
    if not settings.GEMINI_API_KEY:
        raise LLMProviderError(
            "LLM_PROVIDER=gemini requires GEMINI_API_KEY to be set. "
            "Refusing to construct the Gemini client without credentials."
        )
    from langchain_google_genai import ChatGoogleGenerativeAI  # deferred — heavy import

    kwargs: dict = {
        "model": model or settings.GEMINI_MODEL,
        "temperature": temperature,
        "google_api_key": settings.GEMINI_API_KEY,
    }
    if max_tokens is not None:
        kwargs["max_output_tokens"] = max_tokens
    return ChatGoogleGenerativeAI(**kwargs)


def build_llm(
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> BaseChatModel:
    """Construct the chat model for the configured provider.

    model: provider-native model name; None resolves the provider default
    (OLLAMA LLM_MODEL / OpenAI DEFAULT_MODEL / Groq GROQ_MODEL / Gemini GEMINI_MODEL).
    temperature: clamped by the API layer before reaching the agent graph;
    internal call sites pass their own values (0.0 for deterministic steps).
    """
    temp = temperature if temperature is not None else settings.TEMPERATURE_DEFAULT
    provider = settings.LLM_PROVIDER
    if provider == "openai":
        return _build_openai(model, temp, max_tokens)
    if provider == "ollama":
        return _build_ollama(model, temp, max_tokens)
    if provider == "groq":
        return _build_groq(model, temp, max_tokens)
    if provider == "gemini":
        return _build_gemini(model, temp, max_tokens)
    raise LLMProviderError(
        f"unknown LLM_PROVIDER: {provider!r} (supported: 'openai', 'ollama', 'groq', 'gemini')"
    )
