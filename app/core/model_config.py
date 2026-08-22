"""
Model configuration — the server-side allowlist for generation models.

The client must never be trusted to pick an arbitrary model: only models
listed here (via SUPPORTED_MODELS env) may be selected, and generation
parameters (temperature) are clamped to server-defined bounds.
"""

from __future__ import annotations

import json
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class ModelConfigError(ValueError):
    """Raised when a requested model or generation parameter is invalid."""


def _parse_supported_models(raw: str) -> list[str]:
    try:
        models = json.loads(raw)
    except (ValueError, TypeError):
        logger.warning("SUPPORTED_MODELS is not valid JSON, using default allowlist")
        return ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"]
    if not isinstance(models, list) or not all(isinstance(m, str) and m for m in models):
        logger.warning("SUPPORTED_MODELS is not a list of strings, using default allowlist")
        return ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"]
    return list(dict.fromkeys(models))


if settings.LLM_PROVIDER == "ollama":
    # The Ollama allowlist is the configured local model — nothing else can
    # be requested, because no other model exists in the Ollama server.
    # Never fake OpenAI model names against Ollama.
    SUPPORTED_MODELS: list[str] = [settings.LLM_MODEL]
    DEFAULT_MODEL: str = settings.LLM_MODEL
elif settings.LLM_PROVIDER == "groq":
    # Same principle: the Groq allowlist is the configured model. Client
    # model requests must resolve against it, never arbitrary OpenAI names.
    SUPPORTED_MODELS: list[str] = [settings.GROQ_MODEL]
    DEFAULT_MODEL: str = settings.GROQ_MODEL
elif settings.LLM_PROVIDER == "gemini":
    # Gemini: allowlist of working Google Gemini models.
    SUPPORTED_MODELS: list[str] = [
        settings.GEMINI_MODEL if settings.GEMINI_MODEL else "gemini-3.6-flash",
        "gemini-3.6-flash",
        "gemini-3-flash-preview",
        "gemini-2.5-pro",
    ]
    # Deduplicate while preserving order
    SUPPORTED_MODELS = list(dict.fromkeys(SUPPORTED_MODELS))
    DEFAULT_MODEL: str = SUPPORTED_MODELS[0]
else:
    SUPPORTED_MODELS = _parse_supported_models(settings.SUPPORTED_MODELS)
    DEFAULT_MODEL: str = settings.DEFAULT_MODEL if settings.DEFAULT_MODEL in SUPPORTED_MODELS else SUPPORTED_MODELS[0]


def is_supported_model(model: str | None) -> bool:
    return model in SUPPORTED_MODELS


def resolve_model(model: str | None) -> str:
    """Resolve a client-requested model against the allowlist.

    If the client requests a model that is supported by the active provider,
    return it. Otherwise (if the model is empty, legacy OpenAI, Groq, or any
    stale client-side model name when running a single-model provider like Gemini/Groq),
    gracefully fall back to DEFAULT_MODEL.
    """
    if not model:
        return DEFAULT_MODEL
    if is_supported_model(model):
        return model
    logger.warning(
        "model_fallback provider=%r requested=%r — using default=%r",
        settings.LLM_PROVIDER, model, DEFAULT_MODEL
    )
    return DEFAULT_MODEL


def validate_temperature(temperature: float | None) -> float:
    """Validate and clamp a client-supplied temperature to server bounds."""
    if temperature is None:
        return settings.TEMPERATURE_DEFAULT
    if not isinstance(temperature, (int, float)) or isinstance(temperature, bool):
        raise ModelConfigError("temperature must be a number")
    lo, hi = settings.TEMPERATURE_MIN, settings.TEMPERATURE_MAX
    if temperature < lo or temperature > hi:
        raise ModelConfigError(f"temperature must be between {lo} and {hi}")
    return float(temperature)
