"""Hermetic unit tests for the LLM provider boundary (app/core/llm_provider.py).

No network calls: model construction is side-effect-free, and provider
failures are asserted via raising wrappers. A running Ollama server is never
required here — live behavior lives in tests_live/.
"""

import pytest

from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from app.core import llm_provider
from app.core.config import settings
from app.core.llm_provider import LLMProviderError, build_llm


@pytest.fixture(autouse=True)
def _capture_builders(monkeypatch):
    """Wrap the real builders; record raw args so tests can assert routing
    without any network — construction itself performs no I/O."""
    calls = {"openai": None, "ollama": None}
    real_openai = llm_provider._build_openai
    real_ollama = llm_provider._build_ollama

    def wrap_openai(*args, **kwargs):
        calls["openai"] = (args, kwargs)
        return real_openai(*args, **kwargs)

    def wrap_ollama(*args, **kwargs):
        calls["ollama"] = (args, kwargs)
        return real_ollama(*args, **kwargs)

    monkeypatch.setattr(llm_provider, "_build_openai", wrap_openai)
    monkeypatch.setattr(llm_provider, "_build_ollama", wrap_ollama)
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

    def test_invalid_provider_raises(self, monkeypatch, _capture_builders):
        _set(monkeypatch, LLM_PROVIDER="azure")
        with pytest.raises(LLMProviderError, match="azure"):
            build_llm()


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
