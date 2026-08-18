"""Hermetic unit tests for the LLM provider boundary (app/core/llm_provider.py).

No network calls: model construction is side-effect-free, and provider
failures are asserted via raising wrappers. A running Ollama server is never
required here — live behavior lives in tests_live/.
"""

import pytest

import httpx
import ollama
import openai
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from app.core import llm_provider
from app.core.config import settings
from app.core.llm_provider import (
    APPLICATION_ERROR,
    MODEL_GENERATION_FAILED,
    PROVIDER_UNAVAILABLE,
    STRUCTURED_OUTPUT_FAILED,
    TOOL_CALL_FAILED,
    LLMProviderError,
    build_llm,
    classify_provider_error,
    invoke_model_with_retry,
)


@pytest.fixture(autouse=True)
def _capture_builders(monkeypatch):
    """Wrap the real builders; record raw args so tests can assert routing
    without any network — construction itself performs no I/O."""
    calls = {"openai": None, "ollama": None, "groq": None, "gemini": None}
    real_openai = llm_provider._build_openai
    real_ollama = llm_provider._build_ollama
    real_groq = llm_provider._build_groq
    real_gemini = llm_provider._build_gemini

    def wrap_openai(*args, **kwargs):
        calls["openai"] = (args, kwargs)
        return real_openai(*args, **kwargs)

    def wrap_ollama(*args, **kwargs):
        calls["ollama"] = (args, kwargs)
        return real_ollama(*args, **kwargs)

    def wrap_groq(*args, **kwargs):
        calls["groq"] = (args, kwargs)
        return real_groq(*args, **kwargs)

    def wrap_gemini(*args, **kwargs):
        calls["gemini"] = (args, kwargs)
        return real_gemini(*args, **kwargs)

    monkeypatch.setattr(llm_provider, "_build_openai", wrap_openai)
    monkeypatch.setattr(llm_provider, "_build_ollama", wrap_ollama)
    monkeypatch.setattr(llm_provider, "_build_groq", wrap_groq)
    monkeypatch.setattr(llm_provider, "_build_gemini", wrap_gemini)
    return calls


def _set(monkeypatch, **kwargs):
    for k, v in kwargs.items():
        monkeypatch.setattr(settings, k, v)


class TestProviderSelection:
    def test_ollama_provider_selected(self, monkeypatch, _capture_builders):
        _set(monkeypatch, LLM_PROVIDER="ollama", LLM_MODEL="qwen3:8b", OLLAMA_BASE_URL="http://ollama:11434")
        model = build_llm()
        assert isinstance(model, ChatOllama)
        assert model.model == "qwen3:8b"
        assert _capture_builders["ollama"] is not None
        assert _capture_builders["openai"] is None  # OpenAI never constructed

    def test_ollama_respects_explicit_model(self, monkeypatch, _capture_builders):
        _set(monkeypatch, LLM_PROVIDER="ollama", LLM_MODEL="qwen3:8b")
        model = build_llm(model="qwen3:8b", temperature=0.5)
        assert isinstance(model, ChatOllama)
        assert model.model == "qwen3:8b"
        assert model.temperature == 0.5

    def test_ollama_max_tokens_maps_to_num_predict(self, monkeypatch, _capture_builders):
        _set(monkeypatch, LLM_PROVIDER="ollama")
        model = build_llm(max_tokens=128)
        assert isinstance(model, ChatOllama)
        assert model.num_predict == 128

    def test_openai_provider_selected(self, monkeypatch, _capture_builders):
        _set(monkeypatch, LLM_PROVIDER="openai", OPENAI_API_KEY="test-key")
        model = build_llm()
        assert isinstance(model, ChatOpenAI)
        assert model.openai_api_key.get_secret_value() == "test-key"
        assert _capture_builders["ollama"] is None  # Ollama never constructed

    def test_openai_requires_api_key(self, monkeypatch, _capture_builders):
        _set(monkeypatch, LLM_PROVIDER="openai", OPENAI_API_KEY="")
        with pytest.raises(LLMProviderError, match="OPENAI_API_KEY"):
            build_llm()

    def test_groq_provider_selected(self, monkeypatch, _capture_builders):
        _set(monkeypatch, LLM_PROVIDER="groq", GROQ_API_KEY="test-key", GROQ_MODEL="llama-3.3-70b-versatile")
        model = build_llm()
        assert isinstance(model, ChatOpenAI)
        assert model.model == "llama-3.3-70b-versatile"
        assert model.openai_api_base == "https://api.groq.com/openai/v1"
        assert _capture_builders["groq"] is not None
        assert _capture_builders["ollama"] is None  # Ollama never constructed
        assert _capture_builders["openai"] is None  # OpenAI never constructed

    def test_groq_respects_explicit_model(self, monkeypatch, _capture_builders):
        _set(monkeypatch, LLM_PROVIDER="groq", GROQ_API_KEY="test-key")
        model = build_llm(model="llama-3.1-8b-instant", temperature=0.2)
        assert isinstance(model, ChatOpenAI)
        assert model.model == "llama-3.1-8b-instant"
        assert model.temperature == 0.2

    def test_groq_max_tokens_passthrough(self, monkeypatch, _capture_builders):
        _set(monkeypatch, LLM_PROVIDER="groq", GROQ_API_KEY="test-key")
        model = build_llm(max_tokens=256)
        assert isinstance(model, ChatOpenAI)
        assert model.max_tokens == 256

    def test_groq_requires_api_key(self, monkeypatch, _capture_builders):
        _set(monkeypatch, LLM_PROVIDER="groq", GROQ_API_KEY="")
        with pytest.raises(LLMProviderError, match="GROQ_API_KEY"):
            build_llm()
        # No other provider was attempted.
        assert _capture_builders["ollama"] is None
        assert _capture_builders["openai"] is None

    def test_invalid_provider_raises(self, monkeypatch, _capture_builders):
        _set(monkeypatch, LLM_PROVIDER="azure")
        with pytest.raises(LLMProviderError, match="azure"):
            build_llm()


class TestGeminiProvider:
    def test_gemini_provider_selected(self, monkeypatch, _capture_builders):
        _set(monkeypatch, LLM_PROVIDER="gemini", GEMINI_API_KEY="test-gemini-key", GEMINI_MODEL="gemini-2.0-flash")
        model = build_llm()
        assert isinstance(model, ChatGoogleGenerativeAI)
        assert _capture_builders["gemini"] is not None
        assert _capture_builders["openai"] is None   # OpenAI never constructed
        assert _capture_builders["ollama"] is None   # Ollama never constructed
        assert _capture_builders["groq"] is None     # Groq never constructed

    def test_gemini_uses_configured_model(self, monkeypatch, _capture_builders):
        _set(monkeypatch, LLM_PROVIDER="gemini", GEMINI_API_KEY="test-gemini-key", GEMINI_MODEL="gemini-2.0-flash")
        model = build_llm()
        assert isinstance(model, ChatGoogleGenerativeAI)
        # ChatGoogleGenerativeAI stores the bare model name; 'models/' prefix
        # is added by the SDK internally when making API calls.
        assert model.model == "gemini-2.0-flash"

    def test_gemini_respects_explicit_model(self, monkeypatch, _capture_builders):
        _set(monkeypatch, LLM_PROVIDER="gemini", GEMINI_API_KEY="test-gemini-key", GEMINI_MODEL="gemini-2.0-flash")
        model = build_llm(model="gemini-2.5-flash", temperature=0.3)
        assert isinstance(model, ChatGoogleGenerativeAI)
        assert model.model == "gemini-2.5-flash"
        assert model.temperature == 0.3

    def test_gemini_max_tokens_maps_to_max_output_tokens(self, monkeypatch, _capture_builders):
        _set(monkeypatch, LLM_PROVIDER="gemini", GEMINI_API_KEY="test-gemini-key")
        model = build_llm(max_tokens=512)
        assert isinstance(model, ChatGoogleGenerativeAI)
        assert model.max_output_tokens == 512

    def test_gemini_requires_api_key(self, monkeypatch, _capture_builders):
        _set(monkeypatch, LLM_PROVIDER="gemini", GEMINI_API_KEY="")
        with pytest.raises(LLMProviderError, match="GEMINI_API_KEY"):
            build_llm()
        # No other provider was attempted.
        assert _capture_builders["ollama"] is None
        assert _capture_builders["openai"] is None
        assert _capture_builders["groq"] is None

    def test_gemini_is_streamable(self, monkeypatch, _capture_builders):
        """ChatGoogleGenerativeAI must satisfy the streaming contract the graph uses."""
        _set(monkeypatch, LLM_PROVIDER="gemini", GEMINI_API_KEY="test-gemini-key")
        model = build_llm()
        assert hasattr(model, "stream") and hasattr(model, "astream")

    def test_gemini_supports_bind_tools(self, monkeypatch, _capture_builders):
        """ChatGoogleGenerativeAI must support bind_tools (tool-calling path in graph)."""
        _set(monkeypatch, LLM_PROVIDER="gemini", GEMINI_API_KEY="test-gemini-key")
        model = build_llm()
        assert hasattr(model, "bind_tools")

    def test_gemini_failure_does_not_fallback(self, monkeypatch, _capture_builders):
        """A Gemini construction failure must surface directly, never fall back to another provider."""
        _set(monkeypatch, LLM_PROVIDER="gemini", GEMINI_API_KEY="test-gemini-key")

        def boom(*args, **kwargs):
            raise RuntimeError("gemini down")

        monkeypatch.setattr(llm_provider, "_build_gemini", boom)
        with pytest.raises(RuntimeError, match="gemini down"):
            build_llm()
        assert _capture_builders["openai"] is None
        assert _capture_builders["ollama"] is None
        assert _capture_builders["groq"] is None


class TestNoAutomaticFallback:
    def test_ollama_failure_surfaces(self, monkeypatch, _capture_builders):
        _set(monkeypatch, LLM_PROVIDER="ollama", OPENAI_API_KEY="test-key")

        def boom(*args, **kwargs):
            raise RuntimeError("ollama unreachable")

        monkeypatch.setattr(llm_provider, "_build_ollama", boom)
        with pytest.raises(RuntimeError, match="ollama unreachable"):
            build_llm()
        # OpenAI was never even attempted despite a key being present.
        assert _capture_builders["openai"] is None

    def test_openai_failure_surfaces(self, monkeypatch, _capture_builders):
        _set(monkeypatch, LLM_PROVIDER="openai", OPENAI_API_KEY="test-key")

        def boom(*args, **kwargs):
            raise RuntimeError("openai down")

        monkeypatch.setattr(llm_provider, "_build_openai", boom)
        with pytest.raises(RuntimeError, match="openai down"):
            build_llm()
        assert _capture_builders["ollama"] is None


class TestStreamingContract:
    def test_ollama_llm_is_streamable(self, monkeypatch, _capture_builders):
        """ChatOllama must satisfy the streaming contract the graph uses."""
        _set(monkeypatch, LLM_PROVIDER="ollama", LLM_MODEL="qwen3:8b")
        model = build_llm()
        assert hasattr(model, "stream") and hasattr(model, "astream")


# ---------------------------------------------------------------------------
# Error taxonomy + bounded retry (provider boundary)
# ---------------------------------------------------------------------------

def _req(url="https://api.groq.com/openai/v1/chat/completions") -> httpx.Request:
    return httpx.Request("POST", url)


def _resp(status: int) -> httpx.Response:
    return httpx.Response(status, request=_req())


class _FakeMessage:
    content = "ok"


class _RetryProbe:
    """Configurable fake model for retry-policy tests."""

    def __init__(self):
        self.calls = 0
        self._fail_attempt = None
        self._exc = None
        self._always = None

    def raise_on(self, attempt: int, exc: Exception):
        self._fail_attempt = attempt
        self._exc = exc
        return self

    def always_fail(self, exc: Exception):
        self._always = exc
        return self

    def invoke(self, payload):
        self.calls += 1
        if self._always is not None:
            raise self._always
        if self._fail_attempt == self.calls:
            raise self._exc
        return _FakeMessage()


class TestErrorTaxonomy:
    def test_llm_provider_error_is_non_retryable_unavailable(self):
        info = classify_provider_error(LLMProviderError("LLM_PROVIDER=groq requires GROQ_API_KEY"))
        assert info.code == PROVIDER_UNAVAILABLE
        assert info.retryable is False
        assert "GROQ_API_KEY" not in info.safe_message

    def test_rate_limit_is_retryable_unavailable(self):
        exc = openai.RateLimitError("429 quota", response=_resp(429), body=None)
        info = classify_provider_error(exc)
        assert info.code == PROVIDER_UNAVAILABLE
        assert info.retryable is True

    def test_auth_error_is_not_retryable(self):
        exc = openai.AuthenticationError("401 bad key", response=_resp(401), body=None)
        info = classify_provider_error(exc)
        assert info.code == PROVIDER_UNAVAILABLE
        assert info.retryable is False

    def test_connection_error_is_retryable(self):
        exc = openai.APIConnectionError(message="connect failed", request=_req())
        info = classify_provider_error(exc)
        assert info.code == PROVIDER_UNAVAILABLE
        assert info.retryable is True

    def test_groq_tool_use_failed_maps_to_tool_call_failed_retryable(self):
        body = {"error": {"message": "Failed to call a function. Please adjust your prompt. See 'failed_generation' for more details.", "type": "invalid_request_error", "code": "tool_use_failed"}}
        exc = openai.BadRequestError("Failed to call a function.", response=_resp(400), body=body)
        info = classify_provider_error(exc, provider="groq")
        assert info.code == TOOL_CALL_FAILED
        assert info.retryable is True
        # The raw provider text must never leak into the safe message.
        assert "failed_generation" not in info.safe_message
        assert "Failed to call a function" not in info.safe_message

    def test_generic_bad_request_is_model_generation_failed_non_retryable(self):
        body = {"error": {"message": "something else"}}
        exc = openai.BadRequestError("something else", response=_resp(400), body=body)
        info = classify_provider_error(exc)
        assert info.code == MODEL_GENERATION_FAILED
        assert info.retryable is False

    def test_structured_output_style_bad_request(self):
        body = {"error": {"message": "response_format is not supported", "code": "response_format"}}
        exc = openai.BadRequestError("response_format", response=_resp(400), body=body)
        info = classify_provider_error(exc)
        assert info.code == STRUCTURED_OUTPUT_FAILED
        assert info.retryable is False

    def test_not_found_model_is_generation_failed(self):
        exc = openai.NotFoundError("model not found", response=_resp(404), body=None)
        info = classify_provider_error(exc)
        assert info.code == MODEL_GENERATION_FAILED
        assert info.retryable is False

    def test_ollama_server_error_is_retryable_unavailable(self):
        exc = ollama.ResponseError("upstream error", status_code=503)
        info = classify_provider_error(exc, provider="ollama")
        assert info.code == PROVIDER_UNAVAILABLE
        assert info.retryable is True

    def test_ollama_tool_400_is_tool_call_failed_retryable(self):
        exc = ollama.ResponseError("tool error", status_code=400)
        info = classify_provider_error(exc, provider="ollama")
        assert info.code == TOOL_CALL_FAILED
        assert info.retryable is True

    def test_httpx_transport_error_is_retryable(self):
        exc = httpx.ConnectError("refused", request=_req())
        info = classify_provider_error(exc)
        assert info.code == PROVIDER_UNAVAILABLE
        assert info.retryable is True

    def test_unknown_error_is_application_error_non_retryable(self):
        info = classify_provider_error(RuntimeError("db exploded"))
        assert info.code == APPLICATION_ERROR
        assert info.retryable is False
        assert "db exploded" not in info.safe_message


class TestBoundedRetry:
    def test_retryable_error_retries_once_then_succeeds(self):  # proof A
        probe = _RetryProbe().raise_on(1, openai.RateLimitError("429", response=_resp(429), body=None))
        result = invoke_model_with_retry(probe, [], provider="groq")
        assert result.content == "ok"
        assert probe.calls == 2

    def test_retryable_tool_failure_retries_once_then_succeeds(self):  # proof A (Groq)
        body = {"error": {"code": "tool_use_failed", "message": "failed_generation"}}
        probe = _RetryProbe().raise_on(1, openai.BadRequestError("tool fail", response=_resp(400), body=body))
        result = invoke_model_with_retry(probe, [], provider="groq")
        assert result.content == "ok"
        assert probe.calls == 2

    def test_retry_exhaustion_raises_original_and_never_more_than_two(self):  # proofs B + D
        exc = openai.RateLimitError("429", response=_resp(429), body=None)
        probe = _RetryProbe().always_fail(exc)
        calls_before = probe.calls
        with pytest.raises(openai.RateLimitError):
            invoke_model_with_retry(probe, [], provider="groq")
        assert probe.calls - calls_before == 2  # exactly one retry, never more

    def test_non_retryable_error_never_retried(self):  # proof C
        exc = openai.AuthenticationError("401", response=_resp(401), body=None)
        probe = _RetryProbe().raise_on(1, exc)
        with pytest.raises(openai.AuthenticationError):
            invoke_model_with_retry(probe, [], provider="groq")
        assert probe.calls == 1

    def test_application_error_never_retried(self):  # proof C (deterministic)
        probe = _RetryProbe().raise_on(1, ValueError("bad state"))
        with pytest.raises(ValueError):
            invoke_model_with_retry(probe, [], provider="groq")
        assert probe.calls == 1

    def test_success_is_never_retried(self):  # proof E (no duplicate generation)
        probe = _RetryProbe()
        result = invoke_model_with_retry(probe, [], provider="groq")
        assert result.content == "ok"
        assert probe.calls == 1

    def test_retry_never_switches_provider(self):
        captured = []

        class _Tracking:
            calls = 0

            def invoke(self, payload):
                captured.append(self)
                raise openai.RateLimitError("429", response=_resp(429), body=None)

        model = _Tracking()
        with pytest.raises(openai.RateLimitError):
            invoke_model_with_retry(model, [], provider="groq")
        assert len(captured) == 2
        assert captured[0] is captured[1]  # same instance — same provider


# ---------------------------------------------------------------------------
# Provider-resolution compatibility proofs G/H/I (existing selection tests
# above cover construction; these assert the retry/taxonomy boundary does not
# change provider routing).
# ---------------------------------------------------------------------------

class TestGeminiErrorTaxonomy:
    """Gemini error classification via google.api_core.exceptions."""

    def test_gemini_unauthenticated_is_non_retryable(self):
        import google.api_core.exceptions as gexc
        exc = gexc.Unauthenticated("401 bad key")
        info = classify_provider_error(exc, provider="gemini")
        assert info.code == PROVIDER_UNAVAILABLE
        assert info.retryable is False
        assert "bad key" not in info.safe_message

    def test_gemini_resource_exhausted_is_retryable(self):
        import google.api_core.exceptions as gexc
        exc = gexc.ResourceExhausted("429 quota exceeded")
        info = classify_provider_error(exc, provider="gemini")
        assert info.code == PROVIDER_UNAVAILABLE
        assert info.retryable is True

    def test_gemini_service_unavailable_is_retryable(self):
        import google.api_core.exceptions as gexc
        exc = gexc.ServiceUnavailable("503 down")
        info = classify_provider_error(exc, provider="gemini")
        assert info.code == PROVIDER_UNAVAILABLE
        assert info.retryable is True

    def test_gemini_deadline_exceeded_is_retryable(self):
        import google.api_core.exceptions as gexc
        exc = gexc.DeadlineExceeded("504 timeout")
        info = classify_provider_error(exc, provider="gemini")
        assert info.code == PROVIDER_UNAVAILABLE
        assert info.retryable is True

    def test_gemini_tool_invalid_argument_maps_to_tool_call_failed(self):
        import google.api_core.exceptions as gexc
        exc = gexc.InvalidArgument("tool call failed: function parse error")
        info = classify_provider_error(exc, provider="gemini")
        assert info.code == TOOL_CALL_FAILED
        assert info.retryable is True
        assert "function parse error" not in info.safe_message

    def test_gemini_not_found_maps_to_model_generation_failed(self):
        import google.api_core.exceptions as gexc
        exc = gexc.NotFound("model not found")
        info = classify_provider_error(exc, provider="gemini")
        assert info.code == MODEL_GENERATION_FAILED
        assert info.retryable is False

    def test_gemini_generic_api_error_maps_to_provider_unavailable(self):
        import google.api_core.exceptions as gexc
        exc = gexc.GoogleAPICallError("unknown error")
        info = classify_provider_error(exc, provider="gemini")
        assert info.code == PROVIDER_UNAVAILABLE


class TestProviderBoundaryCompatibility:
    def test_openai_routing_unchanged(self, monkeypatch, _capture_builders):
        _set(monkeypatch, LLM_PROVIDER="openai", OPENAI_API_KEY="test-key")
        model = build_llm()
        assert isinstance(model, ChatOpenAI)
        assert _capture_builders["openai"] is not None

    def test_groq_routing_unchanged(self, monkeypatch, _capture_builders):
        _set(monkeypatch, LLM_PROVIDER="groq", GROQ_API_KEY="test-key", GROQ_MODEL="llama-3.3-70b-versatile")
        model = build_llm()
        assert isinstance(model, ChatOpenAI)
        assert model.openai_api_base == "https://api.groq.com/openai/v1"

    def test_ollama_routing_unchanged(self, monkeypatch, _capture_builders):
        _set(monkeypatch, LLM_PROVIDER="ollama", LLM_MODEL="qwen3:8b")
        model = build_llm()
        assert isinstance(model, ChatOllama)
        assert model.model == "qwen3:8b"

    def test_gemini_routing_correct(self, monkeypatch, _capture_builders):
        _set(monkeypatch, LLM_PROVIDER="gemini", GEMINI_API_KEY="test-key", GEMINI_MODEL="gemini-2.0-flash")
        model = build_llm()
        assert isinstance(model, ChatGoogleGenerativeAI)
        assert _capture_builders["gemini"] is not None
        assert _capture_builders["openai"] is None
        assert _capture_builders["ollama"] is None
        assert _capture_builders["groq"] is None
