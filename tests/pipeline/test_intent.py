"""Tests for Stage 1: Intent Classification"""
import pytest
from app.agent.pipeline.intent import IntentClassifier, Intent, IntentResult


class TestIntentClassifier:
    @pytest.fixture
    def classifier(self):
        return IntentClassifier()

    def test_general_greeting(self, classifier):
        result = classifier.classify("hello")
        assert result.intent == Intent.GENERAL
        assert result.confidence > 0.9
        assert not result.used_llm

    def test_general_thanks(self, classifier):
        result = classifier.classify("thanks")
        assert result.intent == Intent.GENERAL
        assert not result.used_llm

    def test_memory_remember(self, classifier):
        result = classifier.classify("remember my name is Alice")
        assert result.intent == Intent.MEMORY
        assert not result.used_llm

    @pytest.mark.parametrize("query", [
        "what is my name?",
        "what's my name",
        "what did I say about the parser",
        "do you remember what I like?",
        "call me Akhi",
        "what are we building in this conversation?",
        "what did we discuss last time?",
        "in this chat we agreed on the plan",
    ])
    def test_memory_recall(self, classifier, query):
        result = classifier.classify(query)
        assert result.intent == Intent.MEMORY
        assert not result.used_llm

    def test_coding_request(self, classifier):
        result = classifier.classify("write a python function to sort a list")
        assert result.intent == Intent.CODING
        assert not result.used_llm

    def test_rag_document(self, classifier):
        result = classifier.classify("what does the document say about pricing")
        assert result.intent == Intent.KNOWLEDGE
        assert not result.used_llm


    def test_reasoning_proof(self, classifier):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(classifier, "_llm_classify", lambda q: IntentResult(
                intent=Intent.REASONING, confidence=0.9, reason="test",
                latency_ms=0.0, used_llm=True,
            ))
            result = classifier.classify("prove that the square root of 2 is irrational step by step")
        assert result.intent == Intent.REASONING
        assert result.used_llm

    def test_bye(self, classifier):
        result = classifier.classify("goodbye")
        assert result.intent == Intent.GENERAL
        assert not result.used_llm

    def test_empty_query_triggers_unknown(self, classifier):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(classifier, "_rule_classify", lambda q: None)
            mp.setattr(classifier, "_llm_classify", lambda q: IntentResult(
                intent=Intent.UNKNOWN, confidence=0.5, reason="fallback",
                latency_ms=0.0, used_llm=True,
            ))
            result = classifier.classify("some ambiguous query")
            assert result.used_llm

    def test_classify_sets_latency(self, classifier):
        result = classifier.classify("hello")
        assert result.latency_ms >= 0
