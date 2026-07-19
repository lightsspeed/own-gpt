import logging
import traceback
import re
import asyncio
import json
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
from langchain_core.messages import HumanMessage
from app.agent.graph import graph, pool
from app.core.database import get_db
from app.models.chat import ChatSession
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from datetime import datetime
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)
router = APIRouter()


class ImageAttachment(BaseModel):
    base64: str
    mimeType: str  # e.g. "image/jpeg"
    name: str


class ChatRequest(BaseModel):
    session_id: str
    message: str
    system_prompt: Optional[str] = None
    images: Optional[List[ImageAttachment]] = None


class ResourceItem(BaseModel):
    type: str  # "web" | "file"
    title: str
    url: Optional[str] = None
    snippet: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str
    response: str
    resources: List[ResourceItem] = []


class HistoryMessage(BaseModel):
    role: str   # "user" | "assistant"
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


def _extract_resources(messages_subset) -> List[ResourceItem]:
    resources = []
    seen = set()
    for msg in messages_subset:
        if type(msg).__name__ == "ToolMessage":
            content = str(msg.content)
            # Split into chunks by standard separators
            parts = re.split(r"---|\n\n", content)
            for part in parts:
                match = re.search(r"Source:\s*([^\n]+)", part)
                if match:
                    title = match.group(1).strip()
                    if title in seen:
                        continue
                    seen.add(title)
                    # Extract snippet: clean up lines and join
                    snippet_lines = []
                    for line in part.split("\n"):
                        clean = line.strip()
                        if clean and not clean.startswith("Source:") and not clean.startswith("Found the following") and not clean.startswith("Web search results:"):
                            # Remove markdown bold/header markers for snippet
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


async def _generate_session_title(message: str) -> str:
    try:
        from langchain_core.messages import SystemMessage, HumanMessage
        title_model = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        res = await title_model.ainvoke([
            SystemMessage(content="You are a helpful assistant. Summarize the user's query in 3 to 5 words to use as a conversation title. Output ONLY the title, no punctuation, no quotes, no extra text."),
            HumanMessage(content=message)
        ])
        title = res.content.strip().replace('"', '').replace("'", "")
        return title[:50]
    except Exception as e:
        logger.error(f"Error generating session title: {e}")
        return message[:30] + "..." if len(message) > 30 else message


# ---------------------------------------------------------------------------
# POST /chat  – send a message; the checkpointer handles multi-turn context
# ---------------------------------------------------------------------------
@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    """
    Sends a new message to the LangGraph agent.
    The PostgreSQL checkpointer automatically loads the full conversation
    history for the given session_id (thread_id), so every request has
    complete multi-turn context.
    """
    try:
        # Get existing state length to know which new messages were added
        config = {"configurable": {"thread_id": request.session_id}}
        existing_state = graph.get_state(config)
        existing_len = len(existing_state.values.get("messages", [])) if existing_state and existing_state.values else 0

        # Upsert the session: look it up first, update or create
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

        initial_state = {
            "messages": [HumanMessage(content=request.message)],
            "system_prompt": request.system_prompt
        }

        final_state = graph.invoke(initial_state, config=config)
        
        # Extract new messages generated in this turn
        new_messages = final_state["messages"][existing_len:]
        last_message = final_state["messages"][-1]
        
        resources = _extract_resources(new_messages)

        return ChatResponse(
            session_id=request.session_id,
            response=last_message.content,
            resources=resources
        )
    except Exception as e:
        logger.error("Chat endpoint error: %s\n%s", str(e), traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# GET /chat/sessions  – list all chat sessions (threads) - MUST be before /{session_id}
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
# PATCH /chat/sessions/{session_id}  – update a chat session (title, pin state)
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
# GET /chat/{session_id}/history  – load past messages for a session
# ---------------------------------------------------------------------------
@router.get("/chat/{session_id}/history", response_model=HistoryResponse)
async def get_history(session_id: str):
    """
    Returns the full conversation history for a given session_id.
    Reads directly from the LangGraph PostgreSQL checkpoint store.
    """
    try:
        config = {"configurable": {"thread_id": session_id}}
        state = graph.get_state(config)

        messages: List[HistoryMessage] = []
        if state and state.values:
            all_messages = state.values.get("messages", [])
            
            # We want to attach resources to AIMessages. We'll track ToolMessages seen *after* a HumanMessage
            # and attach them to the *next* AIMessage.
            current_resources = []
            
            for msg in all_messages:
                msg_type = type(msg).__name__
                if msg_type == "HumanMessage":
                    messages.append(HistoryMessage(role="user", content=msg.content))
                    current_resources = []
                elif msg_type == "ToolMessage":
                    current_resources.extend(_extract_resources([msg]))
                elif msg_type == "AIMessage" and msg.content:
                    messages.append(HistoryMessage(
                        role="assistant", 
                        content=msg.content, 
                        resources=current_resources
                    ))
                    current_resources = []

        return HistoryResponse(session_id=session_id, messages=messages)
    except Exception as e:
        logger.error("History endpoint error: %s\n%s", str(e), traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))




# ---------------------------------------------------------------------------
# DELETE /chat/sessions/{session_id}  – delete a chat session
# ---------------------------------------------------------------------------
@router.delete("/chat/sessions/{session_id}")
async def delete_session(session_id: str, db: AsyncSession = Depends(get_db)):
    try:
        stmt = delete(ChatSession).where(ChatSession.id == session_id)
        await db.execute(stmt)
        await db.commit()
        
        # Clean from LangGraph checkpointer
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
    """
    Sends a new message to the LangGraph agent and streams the output tokens
    along with tool calling status and final resource citations.
    """
    try:
        config = {"configurable": {"thread_id": request.session_id}}
        existing_state = await asyncio.to_thread(graph.get_state, config)
        existing_len = len(existing_state.values.get("messages", [])) if existing_state and existing_state.values else 0

        # Upsert the session: look it up first, update or create
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

        # Build the message content — multimodal when images are present
        if request.images:
            content: list = [{"type": "text", "text": request.message}]
            for img in request.images:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{img.mimeType};base64,{img.base64}"}
                })
            human_message = HumanMessage(content=content)
        else:
            human_message = HumanMessage(content=request.message)

        initial_state = {
            "messages": [human_message],
            "system_prompt": request.system_prompt
        }

        # Use a queue to bridge sync checkpointer streaming and async FastAPI
        q: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_event_loop()

        def stream_in_thread():
            """Run the synchronous LangGraph streaming in a background thread."""
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

                # Extract citations after streaming completes
                final_state = graph.get_state(config)
                if final_state and final_state.values:
                    new_msgs = final_state.values.get("messages", [])[existing_len:]
                    resources = _extract_resources(new_msgs)
                    serialized = [{"type": r.type, "title": r.title, "url": r.url, "snippet": r.snippet} for r in resources]
                    if serialized:
                        loop.call_soon_threadsafe(q.put_nowait, json.dumps({"type": "resources", "resources": serialized}))
            except Exception as thread_err:
                logger.error(f"Stream thread error: {thread_err}", exc_info=True)
                loop.call_soon_threadsafe(q.put_nowait, json.dumps({"type": "error", "message": str(thread_err)}))
            finally:
                loop.call_soon_threadsafe(q.put_nowait, "[DONE]")

        async def event_generator():
            # Start the sync streaming in a background thread
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
