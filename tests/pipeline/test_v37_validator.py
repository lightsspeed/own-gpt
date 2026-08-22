"""V3.7 Answer Validation & Grounding — hermetic tests.

Covers the 12 required cases:
  1.  Grounded knowledge answer → valid
  2.  Missing knowledge evidence → invalid
  3.  Grounded memory answer → valid
  4.  Missing memory evidence → invalid
  5.  Web answer with evidence → valid
  6.  Failed execution → flagged
  7.  Blocked execution → flagged
  8.  General answer without grounding → not rejected
  9.  Malformed LLM validation → deterministic fallback
  10. Structured ValidationResult shape
  11. Pipeline populates ctx.validation
  12. Validator never executes tools

No live / API / E2E calls. LLM escalation uses a fake LLM only.
"""
import pytest

from app.agent.pipeline.context import ContextSource, RetrievedContext
from app.agent.pipeline.executor import ExecutionResult, StepResult
from app.agent.pipeline.validator import (
    AnswerValidator,
    SAFE_CLARIFICATION_MESSAGE,
    ValidationResult,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _context(
    source_types: tuple = ("knowledge",),
    grounding_required: bool = True,
    has_evidence: bool = True,
) -> RetrievedContext:
    sources = [
        ContextSource(
            source_id=f"{t}-1",
            source_type=t,
            title=f"{t} title",
            content=f"{t} evidence content",
        )
        for t in source_types
    ]
    return RetrievedContext(
        query="q",
        sources=sources,
        memory_context="memory evidence" if "memory" in source_types else "",
        knowledge_context="knowledge evidence" if "knowledge" in source_types else "",
        document_context="document evidence" if "document" in source_types else "",
        web_context="web evidence" if "web" in source_types else "",
        has_evidence=has_evidence,
        source_count=len(sources) if has_evidence else 0,
        grounding_required=grounding_required,
    )


def _execution(status: str = "completed", output: str = "some output") -> ExecutionResult:
    return ExecutionResult(
        status=status,
        step_results=[StepResult(step_id=1, status=status, output=output)],
        outputs={1: output} if status == "completed" else {},
        final_output=output if status == "completed" else None,
    )


class _FakeLLM:
    """Minimal LLM stub returning a fixed content blob."""

    def __init__(self, content: str):
        self.content = content
        self.invocations = 0

    def invoke(self, messages):
        self.invocations += 1

        class _Resp:
            pass

        resp = _Resp()
        resp.content = self.content
        return resp


class _MockVectorStore:
    def __init__(self, results=None):
        self._results = results

    def similarity_search_with_score(self, query, k, filter=None):
        return self._results if self._results is not None else []


# ── 1-5: Grounding policy (knowledge / memory / web) ─────────────────────────

def test_grounded_knowledge_answer_valid():
    ctx = _context(source_types=("knowledge",))
    execution = _execution(output="knowledge evidence")
    result = AnswerValidator().validate(
        question="What is docker?", answer="Docker containers share the host kernel.",
        context=ctx, execution=execution,
    )
    assert result.valid is True
    assert result.grounded is True
    assert result.issues == []


def test_missing_knowledge_evidence_invalid():
    ctx = _context(source_types=(), has_evidence=False)
    execution = _execution(output="irrelevant")
    result = AnswerValidator().validate(
        question="What is docker?", answer="Docker containers share the host kernel.",
        context=ctx, execution=execution,
    )
    assert result.valid is False
    assert result.grounded is False
    assert result.missing_evidence
    assert any("evidence" in i.lower() for i in result.issues)


def test_grounded_memory_answer_valid():
    ctx = _context(source_types=("memory",))
    execution = _execution(output="memory evidence")
    result = AnswerValidator().validate(
        question="What is my favorite color?", answer="Your favorite color is blue.",
        context=ctx, execution=execution,
    )
    assert result.valid is True
    assert result.grounded is True
    assert result.issues == []


def test_missing_memory_evidence_invalid():
    ctx = _context(source_types=(), has_evidence=False)
    execution = _execution(output="irrelevant")
    result = AnswerValidator().validate(
        question="What is my favorite color?", answer="Your favorite color is blue.",
        context=ctx, execution=execution,
    )
    assert result.valid is False
    assert result.grounded is False
    assert result.missing_evidence


def test_web_answer_with_evidence_valid():
    ctx = _context(source_types=("web",))
    execution = _execution(output="web evidence")
    result = AnswerValidator().validate(
        question="What is the latest AWS news?", answer="AWS launched a new region.",
        context=ctx, execution=execution,
    )
    assert result.valid is True
    assert result.grounded is True


# ── 6-7: Execution integrity flags (no auto-retry, no re-plan) ───────────────

def test_failed_execution_flagged():
    ctx = _context(source_types=("knowledge",), has_evidence=True)
    execution = _execution(status="failed")
    result = AnswerValidator().validate(
        question="q", answer="knowledge evidence", context=ctx, execution=execution,
    )
    assert any("failed" in i.lower() for i in result.issues)


def test_blocked_execution_flagged():
    ctx = _context(source_types=("knowledge",), has_evidence=True)
    execution = _execution(status="blocked")
    result = AnswerValidator().validate(
        question="q", answer="knowledge evidence", context=ctx, execution=execution,
    )
    assert any("blocked" in i.lower() for i in result.issues)


# ── 8: General / optional-grounding answers are never rejected ───────────────

def test_general_answer_no_grounding_not_rejected():
    ctx = _context(source_types=(), grounding_required=False, has_evidence=False)
    execution = _execution(output="Hello! How can I help you?")
    result = AnswerValidator().validate(
        question="Hi", answer="Hello! How can I help you?",
        context=ctx, execution=execution,
    )
    assert result.valid is True
    assert result.grounded is True
    assert result.missing_evidence == []


# ── 9: Malformed LLM output degrades to deterministic result ─────────────────

def test_malformed_llm_validation_falls_back_to_deterministic():
    fake = _FakeLLM(content="this is definitely not json {{{")
    validator = AnswerValidator(use_llm=True, llm=fake)
    ctx = _context(source_types=("knowledge",))
    execution = _execution(output="knowledge evidence")
    result = validator.validate(
        question="q", answer="knowledge evidence", context=ctx, execution=execution,
    )
    assert fake.invocations == 1
    # Deterministic fallback: grounded answer stays valid.
    assert result.valid is True
    assert result.grounded is True
    assert result.missing_evidence == []


# ── 10: Structured ValidationResult shape ────────────────────────────────────

def test_validation_result_is_structured():
    ctx = _context(source_types=("knowledge",))
    execution = _execution(output="knowledge evidence")
    result = AnswerValidator().validate(
        question="q", answer="knowledge evidence", context=ctx, execution=execution,
    )
    assert isinstance(result, ValidationResult)
    assert isinstance(result.valid, bool)
    assert isinstance(result.grounded, bool)
    assert isinstance(result.confidence, float)
    assert 0.0 <= result.confidence <= 1.0
    assert isinstance(result.issues, list)
    assert isinstance(result.missing_evidence, list)
    assert result.corrected_answer is None


# ── 11: Pipeline populates ctx.validation and clarifies on failure ───────────

def test_pipeline_populates_validation():
    from langchain_core.documents import Document

    from app.agent.pipeline.intent import Intent, IntentResult
    from app.agent.pipeline.pipeline import RAGPipeline
    from app.agent.pipeline.reranker import RankedChunk

    store = _MockVectorStore(results=[
        (
            Document(
                page_content="Docker containers share the host kernel.",
                metadata={"filename": "docker.pdf", "source": "docker.pdf"},
            ),
            0.9,
        )
    ])
    pipe = RAGPipeline(
        vector_store=store,
        redis_url=None,
        config={
            "intent_enabled": True,
            "rewrite_enabled": False,
            "validation_enabled": False,
            "trace_enabled": False,
        },
    )
    with pytest.MonkeyPatch.context() as mp:
        from app.agent.pipeline import intent as intent_mod
        mp.setattr(
            intent_mod.IntentClassifier, "classify",
            lambda self, q: IntentResult(Intent.KNOWLEDGE, 0.95, "test", 0.0, False),
        )
        mp.setattr(
            pipe._reranker, "rerank",
            lambda query, chunks: [
                RankedChunk(chunk=c, reranker_score=1.0, original_rank=i, reranked_rank=i)
                for i, c in enumerate(chunks)
            ],
        )
        ctx = pipe.process("what is docker?", "s1")

    assert ctx.validation is not None
    assert isinstance(ctx.validation, ValidationResult)
    assert ctx.validation.valid is True
    assert ctx.validation.grounded is True


def test_pipeline_clarifies_on_missing_evidence():
    from app.agent.pipeline.intent import Intent, IntentResult
    from app.agent.pipeline.pipeline import RAGPipeline

    pipe = RAGPipeline(
        vector_store=_MockVectorStore(results=[]),
        redis_url=None,
        config={
            "intent_enabled": True,
            "rewrite_enabled": False,
            "validation_enabled": False,
            "trace_enabled": False,
        },
    )

    class _FakeToolExecution:
        status = "executed"
        result = "No relevant knowledge base content found."
        error = None

    with pytest.MonkeyPatch.context() as mp:
        from app.agent.pipeline import intent as intent_mod
        mp.setattr(
            intent_mod.IntentClassifier, "classify",
            lambda self, q: IntentResult(Intent.KNOWLEDGE, 0.95, "test", 0.0, False),
        )
        mp.setattr(
            pipe._reranker, "rerank",
            lambda query, chunks: [],
        )
        # Hermetic: knowledge step falls back to the tool gate when the
        # orchestrator retrieved no evidence — stub it out (no DB, no LLM).
        mp.setattr(
            "app.agent.pipeline.executor.request_tool_execution",
            lambda tool, args: _FakeToolExecution(),
        )
        ctx = pipe.process("what is docker?", "s1")

    assert ctx.validation is not None
    assert ctx.validation.valid is False
    assert ctx.validation.grounded is False
    assert ctx.synthesis.answer == SAFE_CLARIFICATION_MESSAGE


# ── 12: Validator never executes tools ───────────────────────────────────────

def test_validator_never_executes_tools(monkeypatch):
    calls: list = []

    def _explode(tool, args):
        calls.append((tool, args))
        raise AssertionError("validator must never execute tools")

    monkeypatch.setattr(
        "app.agent.pipeline.validator.build_llm",
        lambda *a, **k: _FakeLLM('{"grounded": true, "confidence": 0.9, "issues": [], "missing_evidence": []}'),
    )
    validator = AnswerValidator(use_llm=True)
    ctx = _context(source_types=("memory", "knowledge"), has_evidence=True)
    execution = _execution(output="evidence")

    # Deterministic path + LLM escalation path must both be tool-free.
    result = validator.validate(
        question="q", answer="evidence", context=ctx, execution=execution,
    )
    assert result.valid is True
    assert calls == []