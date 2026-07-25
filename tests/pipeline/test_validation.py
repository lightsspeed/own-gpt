"""Tests for Stage 8: Response Validation"""
import pytest
from app.agent.pipeline.validation import ResponseValidator


def _mock_llm_reject(question, response):
    return (False, "LLM rejected")


def _mock_llm_approve(question, response):
    return (True, "LLM approved")


class TestResponseValidator:
    @pytest.fixture
    def validator(self):
        return ResponseValidator()

    def test_valid_response_passes_rules(self, validator):
        result = validator.validate("test question", "A valid response.")
        assert result.valid
        assert not result.used_llm

    def test_empty_response_fails(self, validator):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(validator, "_llm_validate", _mock_llm_reject)
            result = validator.validate("question", "")
        assert not result.valid

    def test_too_short_response_fails(self, validator):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(validator, "_llm_validate", _mock_llm_reject)
            result = validator.validate("question", "ab")
        assert not result.valid

    def test_unmatched_code_fences_fails(self, validator):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(validator, "_llm_validate", _mock_llm_reject)
            result = validator.validate("write code", "```python\nprint('hi')\n```\nmore\n```")
        assert not result.valid

    def test_duplicate_paragraphs_fails(self, validator):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(validator, "_llm_validate", _mock_llm_reject)
            result = validator.validate("question", "Hello.\n\nHello.")
        assert not result.valid

    def test_rule_validation_then_llm_escalation(self, validator):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(validator, "_llm_validate", _mock_llm_reject)
            result = validator.validate("question", "")
            assert result.used_llm

    def test_llm_validation_sets_used_llm_flag(self, validator):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(validator, "_llm_validate", _mock_llm_approve)
            result = validator.validate("question", "")
            assert result.used_llm
