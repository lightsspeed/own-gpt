import logging
import traceback
import re
import asyncio
import json
import time
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
from app.agent.graph import graph, pool
from app.evaluation.models import build_evaluation_result
from app.core.database import get_db
from app.models.chat import ChatSession
from app.agent.pipeline import RAGPipeline, PipelineContext, load_pipeline_config
from app.services.vector_store import vector_store
from app.core.config import settings
from app.learning.telemetry.collector import learning_collector
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from datetime import datetime
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Singleton RAG pipeline — initialized once with config + store
# ---------------------------------------------------------------------------
_pipeline_config = load_pipeline_config()
# Lazy-load Whoosh BM25 retriever for hybrid search
try:
    from app.core.whoosh_manager import get_whoosh_retriever
    _bm25 = get_whoosh_retriever()
    logger.info("rag_pipeline_hybrid_enabled bm25_docs=%d", _bm25.doc_count)
except Exception:
    _bm25 = None
    logger.info("rag_pipeline_hybrid_disabled (no whoosh index)")
_pipeline = RAGPipeline(
    vector_store=vector_store,
    bm25_retriever=_bm25,
    redis_url=settings.REDIS_URL,
    config=_pipeline_config,
)


def _count_tokens(text: str) -> int:
    import tiktoken
    try:
        enc = tiktoken.encoding_for_model("gpt-4o-mini")
        return len(enc.encode(text))
    except Exception:
        return len(text) // 4


class ChatRequest(BaseModel):
    session_id: str
    message: str
    system_prompt: Optional[str] = None
    active_tools: Optional[dict[str, bool]] = None


class ResourceItem(BaseModel):
    type: str
    title: str
    url: Optional[str] = None
    snippet: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    response: str
    resources: List[ResourceItem] = []
    answer_mode: str = "grounded"


class HistoryMessage(BaseModel):
    role: str
    content: str
    resources: List[ResourceItem] = []


class HistoryResponse(BaseModel):
    session_id: str
    messages: List[HistoryMessage]


class SessionListItem(BaseModel):
    id: str
    title: str
    is_pinned: bool = False
    created_at: datetime
    updated_at: datetime


class SessionUpdateRequest(BaseModel):
    title: Optional[str] = None
    is_pinned: Optional[bool] = None


class SessionListResponse(BaseModel):
    sessions: List[SessionListItem]


class SearchResultItem(BaseModel):
    session_id: str
    session_title: str
    match_type: str  # 'title' | 'message'
    preview: str
    timestamp: datetime


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResultItem]
    total: int


search_logger = logging.getLogger("search")


def _flatten_content(content) -> str:
    """Convert structured content (list of content blocks) to plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
                elif block.get("type") == "image_url":
                    parts.append("[Image]")
                else:
                    parts.append(str(block))
            else:
                parts.append(str(block))
        return "\n".join(p.strip() for p in parts if p.strip())
    return str(content)


def _extract_resources(messages_subset) -> List[ResourceItem]:
    resources = []
    seen = set()
    for msg in messages_subset:
        if type(msg).__name__ == "ToolMessage":
            content = str(msg.content)
            parts = re.split(r"---|\n\n", content)
            for part in parts:
                match = re.search(r"Source:\s*([^\n]+)", part)
                if match:
                    title = match.group(1).strip()
                    if title in seen:
                        continue
                    seen.add(title)
                    snippet_lines = []
                    for line in part.split("\n"):
                        clean = line.strip()
                        if clean and not clean.startswith("Source:") and not clean.startswith("Found the following") and not clean.startswith("Web search results:"):
                            clean = re.sub(r"\*\*|#", "", clean)
                            snippet_lines.append(clean)
                    snippet = " ".join(snippet_lines)[:180]
                    if len(snippet) >= 180:
                        snippet += "..."

                    if title.startswith("http://") or title.startswith("https://"):
                        resources.append(ResourceItem(type="web", title=title, url=title, snippet=snippet))
                    else:
                        resources.append(ResourceItem(type="file", title=title, snippet=snippet))
    return resources


def _extract_tool_names(messages_subset) -> List[str]:
    tools_used = []
    for msg in messages_subset:
        if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                name = tc.get("name") or tc.get("function", {}).get("name", "")
                if name:
                    tools_used.append(name)
    return tools_used


async def _generate_session_title(message: str) -> str:
    try:
        title_model = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        res = await title_model.ainvoke([
            SystemMessage(content="Summarize the user's query in 3 to 5 words as a conversation title. Output ONLY the title, no punctuation, no quotes, no extra text."),
            HumanMessage(content=message)
        ])
        title = res.content.strip().replace('"', '').replace("'", "")
        return title[:50]
    except Exception as e:
        logger.error(f"Error generating session title: {e}")
        return message[:30] + "..." if len(message) > 30 else message


def _run_pipeline(message: str, session_id: str, retriever_mode: Optional[str] = None) -> PipelineContext:
    """Run the pre-processing pipeline. Returns context with intent, route, context_text."""
    return _pipeline.process(question=message, session_id=session_id, retriever_mode=retriever_mode)


def _post_process(ctx: PipelineContext, response: str, new_messages: list) -> None:
    """Validate response, store trace, and record telemetry."""
    ctx.trace.memory_used = True  # memory is always checked in call_model
    ctx.trace.tools_used = _extract_tool_names(new_messages)
    ctx.trace.prompt_tokens = _count_tokens(ctx.question)
    ctx.trace.completion_tokens = _count_tokens(response)

    _pipeline.validate_response(question=ctx.question, response=response, ctx=ctx)

    # Record learning telemetry (fire-and-forget, never blocks the response)
    learning_collector.record(ctx, response)


# ---------------------------------------------------------------------------
# POST /chat  – send a message; the checkpointer handles multi-turn context
# ---------------------------------------------------------------------------
@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    try:
        config = {"configurable": {"thread_id": request.session_id}}
        existing_state = graph.get_state(config)
        existing_len = len(existing_state.values.get("messages", [])) if existing_state and existing_state.values else 0

        # Upsert session
        stmt = select(ChatSession).where(ChatSession.id == request.session_id)
        res = await db.execute(stmt)
        session = res.scalar_one_or_none()

        if session is None:
            title = await _generate_session_title(request.message)
            session = ChatSession(id=request.session_id, title=title)
            db.add(session)
            await db.commit()
        else:
            session.updated_at = datetime.utcnow()
            await db.commit()

        # ── Stage 1-7: Run pre-processing pipeline ────────────────────────────
        ctx = _run_pipeline(request.message, request.session_id)

        # Check if we should short-circuit with clarification
        if ctx.confidence and ctx.confidence.decision == "clarification":
            response = _pipeline.clarification_message()
            if ctx.trace:
                ctx.trace.final_response_len = len(response)
                ctx.trace.total_latency_ms = 0.0
            if _pipeline_config.get("trace_enabled", True):
                _pipeline.tracer.store(ctx.trace)
            return ChatResponse(
                session_id=request.session_id,
                response=response,
                resources=[],
                answer_mode=ctx.answer_mode,
            )

        # Build initial state with pipeline context
        initial_state = {
            "messages": [HumanMessage(content=request.message)],
            "system_prompt": request.system_prompt or "",
            "intent": ctx.intent_label,
            "rewritten_query": ctx.final_query,
            "pipeline_context": ctx.context_text,
        }

        final_state = graph.invoke(initial_state, config=config)

        new_messages = final_state["messages"][existing_len:]
        last_message = final_state["messages"][-1]
        response = last_message.content

        # Filter resources based on answer mode and evidence builder
        evidence_result = _pipeline._evidence_builder.build(
            response_text=response,
            ranked_chunks=ctx.ranked_chunks,
            source_policy=ctx.source_policy,
            answer_mode=ctx.answer_mode,
            answer_mode_metadata=ctx.answer_mode_metadata,
        )
        resources = [
            ResourceItem(type=e.source_type, title=e.title, url=e.url, snippet=e.chunk[:180] if e.chunk else None)
            for e in evidence_result.evidence
        ]

        # ── Stages 8-9: Validate response + store trace ───────────────────────
        _post_process(ctx, response, new_messages)

        return ChatResponse(
            session_id=request.session_id,
            response=response,
            resources=resources,
            answer_mode=ctx.answer_mode,
        )
    except Exception as e:
        logger.error("Chat endpoint error: %s\n%s", str(e), traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# GET /chat/sessions  – list all chat sessions
# ---------------------------------------------------------------------------
@router.get("/chat/sessions", response_model=SessionListResponse)
async def list_sessions(db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(ChatSession).order_by(ChatSession.is_pinned.desc(), ChatSession.updated_at.desc())
        res = await db.execute(stmt)
        sessions = res.scalars().all()
        return SessionListResponse(
            sessions=[
                SessionListItem(
                    id=s.id,
                    title=s.title,
                    is_pinned=s.is_pinned,
                    created_at=s.created_at,
                    updated_at=s.updated_at
                ) for s in sessions
            ]
        )
    except Exception as e:
        logger.error(f"Failed to list sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# GET /chat/search  – search sessions and messages
# ---------------------------------------------------------------------------
@router.get("/chat/search", response_model=SearchResponse)
async def search_conversations(q: str = "", type: str = "all", limit: int = 20, db: AsyncSession = Depends(get_db)):
    try:
        query = q.strip()
        if not query:
            return SearchResponse(query="", results=[], total=0)

        results: List[SearchResultItem] = []

        # Search session titles
        stmt = (
            select(ChatSession)
            .where(ChatSession.title.ilike(f"%{query}%"))
            .order_by(ChatSession.updated_at.desc())
            .limit(limit)
        )
        res = await db.execute(stmt)
        for s in res.scalars().all():
            preview = s.title[:120]
            if query.lower() in preview.lower():
                idx = preview.lower().index(query.lower())
                start = max(0, idx - 30)
                end = min(len(preview), idx + len(query) + 30)
                preview = ("…" if start > 0 else "") + preview[start:end] + ("…" if end < len(preview) else "")
            results.append(SearchResultItem(
                session_id=s.id,
                session_title=s.title,
                match_type="title",
                preview=preview,
                timestamp=s.updated_at or s.created_at,
            ))

        # Search message content via history endpoint per session
        if len(results) < limit:
            msg_stmt = (
                select(ChatSession)
                .order_by(ChatSession.updated_at.desc())
                .limit(limit * 2)
            )
            msg_res = await db.execute(msg_stmt)
            for s in msg_res.scalars().all():
                if len(results) >= limit:
                    break
                if any(r.session_id == s.id for r in results):
                    continue
                try:
                    config = {"configurable": {"thread_id": s.id}}
                    state = graph.get_state(config)
                    if not state or not state.values:
                        continue
                    for msg in state.values.get("messages", []):
                        content = msg.content if isinstance(msg.content, str) else ""
                        if query.lower() in content.lower():
                            idx = content.lower().index(query.lower())
                            start = max(0, idx - 60)
                            end = min(len(content), idx + len(query) + 60)
                            preview = ("…" if start > 0 else "") + content[start:end] + ("…" if end < len(content) else "")
                            results.append(SearchResultItem(
                                session_id=s.id,
                                session_title=s.title,
                                match_type="message",
                                preview=preview,
                                timestamp=s.updated_at or s.created_at,
                            ))
                            break
                except Exception:
                    continue

        search_logger.info("search query=%q hits=%d", query, len(results))
        return SearchResponse(query=query, results=results[:limit], total=len(results))
    except Exception as e:
        logger.error("Search endpoint error: %s\n%s", str(e), traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# PATCH /chat/sessions/{session_id}  – update title / pin state
# ---------------------------------------------------------------------------
@router.patch("/chat/sessions/{session_id}", response_model=SessionListItem)
async def update_session(session_id: str, request: SessionUpdateRequest, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(ChatSession).where(ChatSession.id == session_id)
        res = await db.execute(stmt)
        session = res.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        if request.title is not None:
            session.title = request.title
        if request.is_pinned is not None:
            session.is_pinned = request.is_pinned

        session.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(session)

        return SessionListItem(
            id=session.id,
            title=session.title,
            is_pinned=session.is_pinned,
            created_at=session.created_at,
            updated_at=session.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# GET /chat/{session_id}/history  – load past messages
# ---------------------------------------------------------------------------
@router.get("/chat/{session_id}/history", response_model=HistoryResponse)
async def get_history(session_id: str):
    try:
        config = {"configurable": {"thread_id": session_id}}
        state = graph.get_state(config)

        messages: List[HistoryMessage] = []
        if state and state.values:
            all_messages = state.values.get("messages", [])

            current_resources = []

            for msg in all_messages:
                msg_type = type(msg).__name__
                if msg_type == "HumanMessage":
                    content = msg.content if isinstance(msg.content, str) else _flatten_content(msg.content)
                    messages.append(HistoryMessage(role="user", content=content))
                    current_resources = []
                elif msg_type == "ToolMessage":
                    current_resources.extend(_extract_resources([msg]))
                elif msg_type == "AIMessage" and msg.content:
                    content = msg.content if isinstance(msg.content, str) else _flatten_content(msg.content)
                    messages.append(HistoryMessage(
                        role="assistant",
                        content=content,
                        resources=current_resources
                    ))
                    current_resources = []

        return HistoryResponse(session_id=session_id, messages=messages)
    except Exception as e:
        logger.error("History endpoint error: %s\n%s", str(e), traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# DELETE /chat/sessions/{session_id}
# ---------------------------------------------------------------------------
@router.delete("/chat/sessions/{session_id}")
async def delete_session(session_id: str, db: AsyncSession = Depends(get_db)):
    try:
        stmt = delete(ChatSession).where(ChatSession.id == session_id)
        await db.execute(stmt)
        await db.commit()

        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM checkpoint_writes WHERE thread_id = %s", (session_id,))
                    cur.execute("DELETE FROM checkpoints WHERE thread_id = %s", (session_id,))
                    cur.execute("DELETE FROM checkpoint_blobs WHERE thread_id = %s", (session_id,))
        except Exception as checkpoint_err:
            logger.warning(f"Failed to clean checkpointer tables for {session_id}: {checkpoint_err}")

        return {"status": "deleted"}
    except Exception as e:
        logger.error(f"Failed to delete session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# POST /chat/stream  – send a message and stream the response (SSE)
# ---------------------------------------------------------------------------
@router.post("/chat/stream")
async def chat_stream_endpoint(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    try:
        config = {"configurable": {"thread_id": request.session_id}}
        existing_state = await asyncio.to_thread(graph.get_state, config)
        existing_len = len(existing_state.values.get("messages", [])) if existing_state and existing_state.values else 0

        # Upsert session
        stmt = select(ChatSession).where(ChatSession.id == request.session_id)
        res = await db.execute(stmt)
        session = res.scalar_one_or_none()

        if session is None:
            title = await _generate_session_title(request.message)
            session = ChatSession(id=request.session_id, title=title)
            db.add(session)
            await db.commit()
        else:
            session.updated_at = datetime.utcnow()
            await db.commit()

        # ── Stage 1-7: Run pre-processing pipeline ────────────────────────────
        ctx = _run_pipeline(request.message, request.session_id)

        # Override answer_mode based on active_tools (frontend tool toggles)
        at = request.active_tools or {}
        web_on = at.get("web", False)
        kb_on = at.get("kb", True)
        if web_on and not kb_on:
            ctx.answer_mode = "web"
            ctx.context_text = ""
            ctx.ranked_chunks = []
        elif not web_on and kb_on:
            ctx.answer_mode = "grounded"
        elif not web_on and not kb_on:
            ctx.answer_mode = "synthesis"
            ctx.context_text = ""
            ctx.ranked_chunks = []

        # Short-circuit for clarification
        if ctx.confidence and ctx.confidence.decision == "clarification":
            msg = _pipeline.clarification_message()
            if ctx.trace:
                ctx.trace.final_response_len = len(msg)
                ctx.trace.total_latency_ms = 0.0
            if _pipeline_config.get("trace_enabled", True):
                _pipeline.tracer.store(ctx.trace)

            async def clarify_generator():
                yield f"data: {json.dumps({'type': 'content', 'content': msg})}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                clarify_generator(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

        human_message = HumanMessage(content=request.message)

        initial_state = {
            "messages": [human_message],
            "system_prompt": request.system_prompt or "",
            "intent": ctx.intent_label,
            "rewritten_query": ctx.final_query,
            "pipeline_context": ctx.context_text,
        }

        q: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_event_loop()

        def stream_in_thread():
            try:
                for stream_mode, stream_event in graph.stream(
                    initial_state,
                    config=config,
                    stream_mode=["messages", "updates"]
                ):
                    if stream_mode == "messages":
                        msg_chunk, _ = stream_event
                        if hasattr(msg_chunk, "content") and msg_chunk.content and msg_chunk.type == "AIMessageChunk":
                            loop.call_soon_threadsafe(q.put_nowait, json.dumps({"type": "content", "content": msg_chunk.content}))
                    elif stream_mode == "updates":
                        for node_name, node_output in stream_event.items():
                            if node_name == "tools" and isinstance(node_output, dict):
                                for m in node_output.get("messages", []):
                                    if hasattr(m, "name") and m.name:
                                        loop.call_soon_threadsafe(q.put_nowait, json.dumps({"type": "tool_end", "tool": m.name}))
                            elif node_name == "agent" and isinstance(node_output, dict):
                                for m in node_output.get("messages", []):
                                    if hasattr(m, "tool_calls") and m.tool_calls:
                                        for tc in m.tool_calls:
                                            tname = tc.get("name") or tc.get("function", {}).get("name", "tool")
                                            loop.call_soon_threadsafe(q.put_nowait, json.dumps({"type": "tool_start", "tool": tname}))

                # Post-processing after streaming completes
                final_state = graph.get_state(config)
                if final_state and final_state.values:
                    new_msgs = final_state.values.get("messages", [])[existing_len:]

                    # Extract response text from the last assistant message
                    last_msg = new_msgs[-1] if new_msgs else None
                    response_text = str(last_msg.content) if last_msg and hasattr(last_msg, "content") else ""

                    # Build evidence items from what the LLM actually cited
                    evidence_result = _pipeline._evidence_builder.build(
                        response_text=response_text,
                        ranked_chunks=ctx.ranked_chunks,
                        source_policy=ctx.source_policy,
                        answer_mode=ctx.answer_mode,
                        answer_mode_metadata=ctx.answer_mode_metadata,
                    )
                    evidence_items = evidence_result.evidence

                    serialized = [e.model_dump(exclude={"raw_score", "reranker_score", "retrieval_latency_ms", "embedding_model"}) for e in evidence_items]
                    loop.call_soon_threadsafe(q.put_nowait, json.dumps({
                        "type": "evidence",
                        "evidence": serialized,
                        "answer_mode": ctx.answer_mode,
                    }))
                    # Keep backward-compat resources event
                    loop.call_soon_threadsafe(q.put_nowait, json.dumps({
                        "type": "resources",
                        "resources": [{"type": e.source_type, "title": e.title, "url": e.url, "snippet": e.chunk[:180] if e.chunk else None} for e in evidence_items],
                        "answer_mode": ctx.answer_mode,
                        "answer_mode_metadata": ctx.answer_mode_metadata,
                    }))

                    # Stages 8-9: Validate + trace
                    if response_text:
                        _post_process(ctx, response_text, new_msgs)

                    # Emit trace metadata as final SSE event before [DONE]
                    if ctx.trace:
                        import dataclasses
                        trace_dict = dataclasses.asdict(ctx.trace)
                        # Build rich retrieval context for debugging
                        retrieved_debug = []
                        for rc in ctx.retrieved_chunks[:10]:
                            retrieved_debug.append({
                                "chunk_id": rc.chunk_id,
                                "score": rc.score,
                                "source": rc.source,
                                "page": rc.page,
                                "chapter": rc.chapter,
                                "content_preview": rc.document.page_content[:200],
                            })
                        trace_dict["_retrieved_debug"] = retrieved_debug
                        ranked_debug = []
                        for rk in ctx.ranked_chunks[:5]:
                            ranked_debug.append({
                                "chunk_id": rk.chunk.chunk_id,
                                "reranker_score": rk.reranker_score,
                                "original_rank": rk.original_rank,
                                "content_preview": rk.chunk.document.page_content[:200],
                            })
                        trace_dict["_ranked_debug"] = ranked_debug
                        trace_dict["_context_text"] = ctx.context_text[:500]
                        loop.call_soon_threadsafe(q.put_nowait, json.dumps({"type": "trace", "trace": trace_dict}))
            except Exception as thread_err:
                logger.error(f"Stream thread error: {thread_err}", exc_info=True)
                err_msg = str(thread_err)
                # Friendly message for image-incompatible models
                if "does not support image" in err_msg.lower() or "cannot read" in err_msg.lower():
                    friendly = "This model doesn't support image analysis. Try using a different model (like gpt-4o) for image tasks, or describe the image in text."
                    loop.call_soon_threadsafe(q.put_nowait, json.dumps({"type": "content", "content": friendly}))
                else:
                    loop.call_soon_threadsafe(q.put_nowait, json.dumps({"type": "error", "message": err_msg}))
            finally:
                loop.call_soon_threadsafe(q.put_nowait, "[DONE]")

        async def event_generator():
            asyncio.get_event_loop().run_in_executor(None, stream_in_thread)
            while True:
                item = await q.get()
                if item == "[DONE]":
                    yield "data: [DONE]\n\n"
                    break
                yield f"data: {item}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            }
        )

    except Exception as e:
        logger.error("Chat streaming endpoint error: %s\n%s", str(e), traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# POST /chat/evaluate  – run pipeline + agent, return structured evaluation
# ---------------------------------------------------------------------------
class EvaluateRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    retriever: Optional[str] = None  # "hybrid" | "vector" | "bm25" — runs default if None


@router.post("/chat/evaluate")
async def chat_evaluate_endpoint(request: EvaluateRequest, db: AsyncSession = Depends(get_db)):
    try:
        session_id = request.session_id or f"eval-{int(time.time())}"
        config = {"configurable": {"thread_id": session_id}}
        existing_state = await asyncio.to_thread(graph.get_state, config)
        existing_len = len(existing_state.values.get("messages", [])) if existing_state and existing_state.values else 0

        # Stage 1-7: Run pre-processing pipeline (with optional retriever mode)
        ctx = _run_pipeline(request.message, session_id, retriever_mode=request.retriever)

        # Short-circuit for clarification
        if ctx.confidence and ctx.confidence.decision == "clarification":
            msg = _pipeline.clarification_message()
            if ctx.trace:
                ctx.trace.final_response_len = len(msg)
                ctx.trace.total_latency_ms = 0.0
            if _pipeline_config.get("trace_enabled", True):
                _pipeline.tracer.store(ctx.trace)
            result = build_evaluation_result(ctx, answer=msg)
            return result.to_dict()

        # Build initial state with pipeline context
        initial_state = {
            "messages": [HumanMessage(content=request.message)],
            "system_prompt": "",
            "intent": ctx.intent_label,
            "rewritten_query": ctx.final_query,
            "pipeline_context": ctx.context_text,
        }

        final_state = await asyncio.to_thread(graph.invoke, initial_state, config)

        new_messages = final_state["messages"][existing_len:]
        last_message = final_state["messages"][-1]
        response = last_message.content

        # Stages 8-9: Validate + trace
        # Populate tool/token info
        ctx.trace.memory_used = True
        ctx.trace.tools_used = _extract_tool_names(new_messages)
        ctx.trace.prompt_tokens = _count_tokens(ctx.question)
        ctx.trace.completion_tokens = _count_tokens(response)
        _pipeline.validate_response(question=ctx.question, response=response, ctx=ctx)

        # Build structured result
        result = build_evaluation_result(ctx, answer=response)
        return result.to_dict()

    except Exception as e:
        logger.error("Evaluate endpoint error: %s\n%s", str(e), traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
