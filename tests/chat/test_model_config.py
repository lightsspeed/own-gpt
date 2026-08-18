"""Model allowlist + generation parameter validation."""

from __future__ import annotations

import pytest

from app.core import model_config
from app.core.model_config import ModelConfigError


def test_default_model_in_allowlist():
    assert model_config.DEFAULT_MODEL in model_config.SUPPORTED_MODELS


def test_valid_model_accepted():
    assert model_config.resolve_model("gpt-4o-mini") == "gpt-4o-mini"
    assert model_config.resolve_model(None) == model_config.DEFAULT_MODEL


def test_invalid_model_fallback():
    assert model_config.resolve_model("gpt-99-ultra") == model_config.DEFAULT_MODEL
    assert model_config.resolve_model("bogus/model-name") == model_config.DEFAULT_MODEL
    # empty string means "not provided" → server default
    assert model_config.resolve_model("") == model_config.DEFAULT_MODEL


def test_temperature_bounds():
    assert model_config.validate_temperature(None) == 0.7
    assert model_config.validate_temperature(0.5) == 0.5
    assert model_config.validate_temperature(0) == 0.0
    with pytest.raises(ModelConfigError):
        model_config.validate_temperature(2.5)
    with pytest.raises(ModelConfigError):
        model_config.validate_temperature(-0.1)
    with pytest.raises(ModelConfigError):
        model_config.validate_temperature("hot")