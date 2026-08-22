"""Hermetic unit tests for V3.6 Retrieval & Context Orchestrator.

All tests are fully mocked — zero live API, pgvector DB, Tavily, or LLM calls.
"""

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass

from app.agent.pipeline.context import (
    ContextSource,
    RetrievedContext,
    ContextRequest,
    ContextOrchestrator,
)
from app.agent.pipeline.intent import Intent, IntentResult
from app.agent.pipeline.planner import Plan, PlanStep
from app.agent.pipeline.executor import Executor, ExecutionResult, StepResult
from app.agent.pipeline.synthesizer import Synthesizer
from app.agent.pipeline.pipeline import PipelineContext, RAGPipeline
from app.agent.pipeline.source_policy import AnswerMode, SourcePolicy
from app.agent.pipeline.router import RequestRouter, RouterResult, RouteDecision


# ── Test 1 & 2: general & coding intents → no retrieval requested ────────────

def test_general_coding_no_retrieval():
    orchestrator = ContextOrchestrator()
    req_gen = orchestrator.build_request("hi there", Intent.GENERAL, plan=None)
    assert req_gen.needs_memory is False
    assert req_gen.needs_knowledge is False
    assert req_gen.needs_web is False
    assert req_gen.needs_document is False

    req_code = orchestrator.build_request("write a print hello statement in python", Intent.CODING, plan=None)
    assert req_code.needs_memory is False
    assert req_code.needs_knowledge is False
    assert req_code.needs_web is False
    assert req_code.needs_document is False


# ── Test 3: memory intent → memory retrieval requested ────────────────────────

def test_memory_intent_requests_memory():
    orchestrator = ContextOrchestrator()
    req = orchestrator.build_request("remember that my dog's name is Rex", Intent.MEMORY, plan=None)
    assert req.needs_memory is True
    assert req.needs_knowledge is False


# ── Test 4: knowledge intent → KB retrieval requested ─────────────────────────

def test_knowledge_intent_requests_kb():
    orchestrator = ContextOrchestrator()
    req = orchestrator.build_request("what is kubernetes rbac?", Intent.KNOWLEDGE, plan=None)
    assert req.needs_knowledge is True
    assert req.needs_memory is False


# ── Test 5: web intent → web retrieval requested ──────────────────────────────

def test_web_intent_requests_web():
    orchestrator = ContextOrchestrator()
    req = orchestrator.build_request("what is the latest release of k8s?", Intent.WEB, plan=None)
    assert req.needs_web is True
    assert req.needs_knowledge is False


# ── Test 6: document intent → document retrieval requested ────────────────────

def test_document_intent_requests_document():
    orchestrator = ContextOrchestrator()
    req = orchestrator.build_request("what is in the uploaded file?", Intent.DOCUMENT, plan=None)
    assert req.needs_document is True
    assert req.needs_knowledge is False


# ── Test 7: multi-intent memory + web ─────────────────────────────────────────

def test_multi_intent_memory_web():
    orchestrator = ContextOrchestrator()
    plan = Plan(
        goal="store and search",
        steps=[
            PlanStep(step_id=1, description="store Rex", action="memory"),
            PlanStep(step_id=2, description="search Rex", action="web_search")
        ],
        requires_tools=True
    )
    req = orchestrator.build_request(
        "remember my dog is Rex and search the web for Rex foods",
        Intent.MULTI_INTENT,
        plan=plan
    )
    assert req.needs_memory is True
    assert req.needs_web is True
    assert req.needs_knowledge is False


# ── Test 8: multi-intent knowledge + web ──────────────────────────────────────

def test_multi_intent_kb_web():
    orchestrator = ContextOrchestrator()
    plan = Plan(
        goal="search kb and web",
        steps=[
            PlanStep(step_id=1, description="search RBAC", action="knowledge"),
            PlanStep(step_id=2, description="search web latest", action="web_search")
        ],
        requires_tools=True
    )
    req = orchestrator.build_request(
        "tell me about rbac and what's the latest news",
        Intent.MULTI_INTENT,
        plan=plan
    )
    assert req.needs_knowledge is True
    assert req.needs_web is True
    assert req.needs_memory is False


# ── Test 9: context source normalization ──────────────────────────────────────

def test_context_source_normalization():
    # Verify ContextSource instantiates and holds normalized fields
    source = ContextSource(
        source_id="id-1",
        source_type="knowledge",
        title="rbac_guide.pdf",
        content="RBAC is role-based...",
        score=0.92,
        metadata={"author": "Dev"}
    )
    assert source.source_id == "id-1"
    assert source.source_type == "knowledge"
    assert source.title == "rbac_guide.pdf"
    assert source.content == "RBAC is role-based..."
    assert source.score == 0.92
    assert source.metadata["author"] == "Dev"


# ── Test 10: duplicate source removal ─────────────────────────────────────────

def test_duplicate_source_removal():
    orchestrator = ContextOrchestrator()
    request = ContextRequest(needs_knowledge=True, needs_memory=False, needs_web=False, needs_document=False, query="test")
    pipeline_ctx = MagicMock()
    pipeline_ctx.user_id = "u1"

    mock_retriever = MagicMock()
    # Return two duplicates with the same chunk_id
    mock_chunk = MagicMock()
    mock_chunk.chunk_id = "chunk-1"
    mock_chunk.source = "doc.pdf"
    mock_chunk.document.page_content = "Duplicate content"
    mock_chunk.collection = "default"
    mock_chunk.provenance = {}

    mock_retriever.retrieve.return_value = ([mock_chunk, mock_chunk], {})
    orchestrator.vector_retriever = mock_retriever

    res = orchestrator.retrieve(request, pipeline_ctx)
    assert len(res.sources) == 1
    assert res.source_count == 1


# ── Test 11: source ordering & request overrides ──────────────────────────────

def test_source_ordering_with_overrides():
    orchestrator = ContextOrchestrator()
    # For a web request, web sources should take priority (-1 rank) and be first
    request = ContextRequest(needs_knowledge=True, needs_memory=True, needs_web=True, needs_document=False, query="test")
    pipeline_ctx = MagicMock()
    pipeline_ctx.user_id = "u1"

    # Mock memory retriever
    mock_hit = MagicMock()
    mock_hit.entity.id = "mem-1"
    mock_hit.entity.statement = "Memory fact"
    mock_hit.entity.domain = "semantic"
    mock_hit.entity.authority = "user"
    mock_hit.entity.confidence = 1.0
    mock_hit.score = 0.9

    # Mock KB retriever
    mock_chunk = MagicMock()
    mock_chunk.chunk_id = "kb-1"
    mock_chunk.source = "kb.pdf"
    mock_chunk.document.page_content = "KB fact"
    mock_chunk.collection = "default"
    mock_chunk.provenance = {}

    with patch("app.services.memory.search_memories", return_value=[mock_hit]), \
         patch("app.agent.tool_gate.request_tool_execution") as mock_gate:
        
        mock_exec = MagicMock()
        mock_exec.status = "executed"
        mock_exec.result = "Web search result content"
        mock_gate.return_value = mock_exec

        orchestrator.vector_retriever = MagicMock()
        orchestrator.vector_retriever.retrieve.return_value = ([mock_chunk], {})

        res = orchestrator.retrieve(request, pipeline_ctx)

    # Order of sources after prioritization: web (since needs_web=True override) -> memory (0) -> knowledge (2)
    assert res.sources[0].source_type == "web"
    assert res.sources[1].source_type == "memory"
    assert res.sources[2].source_type == "knowledge"


# ── Test 12: context character limit & truncation ─────────────────────────────

def test_context_character_limit_truncation():
    orchestrator = ContextOrchestrator()
    orchestrator.MAX_CONTEXT_CHARS = 50
    from langchain_core.documents import Document
    from app.agent.pipeline.retriever import RetrievedChunk

    doc1 = Document(page_content="This is a very long chunk content that will exceed 50 characters.")
    mock_chunk1 = RetrievedChunk(
        document=doc1,
        score=0.9,
        source="kb.pdf",
        collection="default"
    )

    orchestrator.vector_retriever = MagicMock()
    orchestrator.vector_retriever.retrieve.return_value = ([mock_chunk1], {})

    request = ContextRequest(needs_knowledge=True, needs_memory=False, needs_web=False, needs_document=False, query="test")
    pipeline_ctx = MagicMock()
    pipeline_ctx.user_id = "u1"
    res = orchestrator.retrieve(request, pipeline_ctx)
    # The source content should be truncated cleanly
    assert len(res.sources[0].content) <= 95  # content + truncation marker
    assert "[Content truncated due to context limit]" in res.sources[0].content


# ── Test 13 & 14: empty retrieval & failure handling ─────────────────────────

def test_empty_retrieval_and_failure_handling():
    orchestrator = ContextOrchestrator()
    request = ContextRequest(needs_knowledge=True, needs_memory=False, needs_web=False, needs_document=False, query="test")
    pipeline_ctx = MagicMock()
    
    # Retriever throws exception
    orchestrator.vector_retriever = MagicMock()
    orchestrator.vector_retriever.retrieve.side_effect = RuntimeError("Database connection timed out")

    # Should run and degrade gracefully without throwing
    res = orchestrator.retrieve(request, pipeline_ctx)
    assert res.has_evidence is False
    assert len(res.sources) == 0


# ── Test 15: user/project isolation propagation ──────────────────────────────

def test_user_project_isolation_propagation():
    orchestrator = ContextOrchestrator()
    request = ContextRequest(needs_memory=True, needs_knowledge=False, needs_web=False, needs_document=False, query="test")
    pipeline_ctx = MagicMock()
    pipeline_ctx.user_id = "target-user-99"
    pipeline_ctx.project_id = "project-123"

    with patch("app.services.memory.search_memories") as mock_search:
        mock_search.return_value = []
        orchestrator.retrieve(request, pipeline_ctx)
        # Verify user_id and project_id are forwarded to the memory search layer
        mock_search.assert_called_once()
        assert mock_search.call_args[1]["user_id"] == "target-user-99"
        assert mock_search.call_args[1]["project_id"] == "project-123"


# ── Test 16: source-policy propagation ────────────────────────────────────────

def test_source_policy_propagation():
    # Verify that RAGPipeline correctly assigns source policy AnswerMode based on plan
    mock_vector_store = MagicMock()
    pipeline = RAGPipeline(vector_store=mock_vector_store, config={"intent_enabled": False, "rewrite_enabled": False})
    
    pipeline._planner = MagicMock()
    pipeline._planner.create_plan.return_value = Plan(goal="kb search", steps=[], requires_tools=False)
    pipeline._planner.plan.return_value = AnswerMode.from_policy(SourcePolicy.KB)
    
    pipeline._executor = MagicMock()
    pipeline._executor.execute.return_value = ExecutionResult(status="completed", step_results=[])
    
    pipeline._synthesizer = MagicMock()
    mock_synth_res = MagicMock()
    mock_synth_res.success = True
    pipeline._synthesizer.synthesize.return_value = mock_synth_res

    ctx = pipeline.process(question="what is rbac?", session_id="sess-1")
    assert ctx.source_policy is not None
    assert ctx.source_policy.policy == SourcePolicy.KB


# ── Test 17: grounding_required ──────────────────────────────────────────────

def test_grounding_required_calculation():
    orchestrator = ContextOrchestrator()
    # general -> false
    req_gen = orchestrator.build_request("hi", Intent.GENERAL, plan=None)
    ctx_gen = orchestrator.retrieve(req_gen, MagicMock())
    assert ctx_gen.grounding_required is False

    # knowledge -> true
    req_kb = orchestrator.build_request("explain rbac", Intent.KNOWLEDGE, plan=None)
    ctx_kb = orchestrator.retrieve(req_kb, MagicMock())
    assert ctx_kb.grounding_required is True


# ── Test 18: to_prompt_context() format ──────────────────────────────────────

def test_to_prompt_context_formatting():
    context = RetrievedContext(
        query="test",
        sources=[],
        memory_context="Rex is user's dog.",
        knowledge_context="RBAC restricts permissions."
    )
    prompt_str = context.to_prompt_context()
    assert "[MEMORY]" in prompt_str
    assert "Rex is user's dog." in prompt_str
    assert "[KNOWLEDGE]" in prompt_str
    assert "RBAC restricts permissions." in prompt_str


# ── Test 19: pipeline populates ctx.context ──────────────────────────────────

def test_pipeline_populates_context():
    mock_vector_store = MagicMock()
    pipeline = RAGPipeline(vector_store=mock_vector_store, config={"intent_enabled": False, "rewrite_enabled": False})
    
    pipeline._planner = MagicMock()
    pipeline._planner.create_plan.return_value = Plan(goal="test", steps=[], requires_tools=False)
    pipeline._planner.plan.return_value = AnswerMode.from_policy(SourcePolicy.NONE)
    
    pipeline._executor = MagicMock()
    pipeline._executor.execute.return_value = ExecutionResult(status="completed", step_results=[])
    
    pipeline._synthesizer = MagicMock()
    mock_synth_res = MagicMock()
    mock_synth_res.success = True
    pipeline._synthesizer.synthesize.return_value = mock_synth_res

    ctx = pipeline.process(question="hi", session_id="sess-1")
    assert ctx.context is not None
    assert isinstance(ctx.context, RetrievedContext)


# ── Test 20: planner remains unaffected ───────────────────────────────────────

def test_planner_remains_unaffected_by_orchestrator():
    # Verify planner doesn't call orchestrator or vector database
    from app.agent.pipeline.planner import Planner
    planner = Planner()
    intent_res = IntentResult(intent=Intent.KNOWLEDGE, confidence=1.0)
    router_res = RouterResult(decision=RouteDecision.RETRIEVAL, skip_retrieval=False, reason="test")
    
    with patch("app.agent.pipeline.context.ContextOrchestrator.retrieve") as mock_retrieve:
        plan = planner.create_plan("hello", intent_res, router_res)
        mock_retrieve.assert_not_called()
        assert isinstance(plan, Plan)


# ── Test 21: executor receives context ────────────────────────────────────────

def test_executor_receives_context():
    # Verify executor has access to ctx.context fields during execute
    executor = Executor()
    plan = Plan(
        goal="Direct answer",
        steps=[PlanStep(step_id=1, description="What is in context?", action="knowledge")],
        requires_tools=False
    )
    
    pipeline_ctx = MagicMock()
    retrieved = RetrievedContext(
        query="test",
        sources=[],
        knowledge_context="PRE_RETRIEVED_KB_FACT_ABC"
    )
    pipeline_ctx.context = retrieved
    
    res = executor.execute(plan, context=pipeline_ctx)
    assert res.status == "completed"
    assert res.step_results[0].output == "PRE_RETRIEVED_KB_FACT_ABC"


# ── Test 22: synthesizer receives context ────────────────────────────────────

def test_synthesizer_receives_context_and_includes_citations():
    synth = Synthesizer()
    plan = Plan(
        goal="kb",
        steps=[PlanStep(step_id=1, description="kb search", action="knowledge")],
        requires_tools=False
    )
    execution = ExecutionResult(
        status="completed",
        step_results=[StepResult(step_id=1, status="completed", output="Yes, RBAC is...")],
        outputs={1: "Yes, RBAC is..."}
    )
    
    # We pass a RetrievedContext carrying a source
    r_context = RetrievedContext(
        query="test",
        sources=[ContextSource(source_id="s1", source_type="knowledge", title="architecture_guide.pdf", content="Yes, RBAC is...")],
        has_evidence=True
    )
    
    res = synth.synthesize("test question", plan, execution, retrieved_context=r_context)
    assert res.success is True
    # The source citation must be propagated into res.sources
    assert "architecture_guide.pdf" in res.sources
