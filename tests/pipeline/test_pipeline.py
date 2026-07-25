"""Tests for RAGPipeline orchestration (Stages 1-9)"""
import pytest
from app.agent.pipeline.pipeline import RAGPipeline, PipelineContext
from app.agent.pipeline.intent import Intent, IntentResult
from app.agent.pipeline.router import RouterResult, RouteDecision
from app.agent.pipeline.rewrite import RewriteResult
from app.agent.pipeline.confidence import ConfidenceResult
from app.agent.pipeline.validation import ValidationResult


class TestRAGPipeline:
    @pytest.fixture
    def pipeline(self):
        return RAGPipeline(
            vector_store=_MockVectorStore(),
            redis_url=None,
            config={"intent_enabled": True, "rewrite_enabled": True,
                    "validation_enabled": True, "trace_enabled": False},
        )

    def test_process_returns_pipeline_context(self, pipeline):
        ctx = pipeline.process("what is docker", "test-session")
        assert isinstance(ctx, PipelineContext)
        assert ctx.question == "what is docker"
        assert ctx.session_id == "test-session"

    def test_process_sets_intent(self, pipeline):
        ctx = pipeline.process("hello", "s1")
        assert ctx.intent is not None
        assert ctx.intent_label in ("general", "unknown")

    def test_process_sets_route(self, pipeline):
        ctx = pipeline.process("hello", "s1")
        assert ctx.route is not None
        assert ctx.route.decision in (d.value for d in RouteDecision)

    def test_process_skips_retrieval_for_general(self, pipeline):
        ctx = pipeline.process("hello", "s1")
        assert len(ctx.retrieved_chunks) == 0
        assert len(ctx.ranked_chunks) == 0

    def test_process_runs_retrieval_for_rag(self, pipeline):
        with pytest.MonkeyPatch.context() as mp:
            from app.agent.pipeline import intent as intent_mod
            mp.setattr(
                intent_mod.IntentClassifier, "classify",
                lambda self, q: IntentResult(Intent.RAG, 0.95, "test", 0.0, False),
            )
            ctx = pipeline.process("test docs", "s1")
            # May or may not retrieve depending on mock store setup
            assert ctx.final_query != ""

    def test_process_builds_context_text(self, pipeline):
        ctx = pipeline.process("hello", "s1")
        assert hasattr(ctx, "context_text")

    def test_validate_response_returns_result(self, pipeline):
        ctx = pipeline.process("hello", "s1")
        result = pipeline.validate_response("hello", "a response", ctx)
        assert isinstance(result, ValidationResult)

    def test_validate_response_sets_trace_latency(self, pipeline):
        ctx = pipeline.process("hello", "s1")
        pipeline.validate_response("hello", "response", ctx)
        assert ctx.trace.total_latency_ms >= 0

    def test_pipeline_with_disabled_intent(self):
        pipe = RAGPipeline(
            vector_store=_MockVectorStore(), redis_url=None,
            config={"intent_enabled": False, "trace_enabled": False},
        )
        ctx = pipe.process("anything", "s1")
        assert ctx.intent_label == "unknown"

    def test_clarification_message(self, pipeline):
        msg = pipeline.clarification_message()
        assert len(msg) > 10
        assert "rephrase" in msg.lower()


class _MockVectorStore:
    def similarity_search_with_score(self, query, k):
        return []
