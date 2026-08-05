import logging
from psycopg_pool import ConnectionPool
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver
from app.agent.state import AgentState
from app.agent.tools import tools
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from app.core.config import settings
import redis

logger = logging.getLogger(__name__)


def _strip_images(content) -> str:
    """Convert structured content blocks to plain text, removing image_url blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
                elif block.get("type") == "image_url":
                    parts.append("[Image removed — model does not support image input]")
                else:
                    parts.append(str(block))
            else:
                parts.append(str(block))
        return "\n".join(p.strip() for p in parts if p.strip())
    return str(content)


DB_CONNINFO = f"host={settings.PG_HOST} port=5432 dbname=owngpt user=postgres password=postgres"

pool = ConnectionPool(
    conninfo=DB_CONNINFO,
    max_size=20,
    kwargs={"autocommit": True, "prepare_threshold": 0},
)

checkpointer = PostgresSaver(pool)
checkpointer.setup()

model = ChatOpenAI(model="gpt-4o-mini", temperature=0.4, openai_api_key=settings.OPENAI_API_KEY)
model_with_tools = model.bind_tools(tools)


def should_continue(state: AgentState) -> str:
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "continue"
    return "end"


def action_node(state: AgentState) -> dict:
    """Execute tool calls through the guarded tool gate.

    Read-only calls run immediately (sandbox-safe); mutating calls are recorded
    as pending and answered with an approval notice — a human operator approves
    them via the operations API before anything side-effectful runs.
    """
    from app.agent.tool_gate import request_tool_execution

    last_message = state["messages"][-1]
    if not (isinstance(last_message, AIMessage) and last_message.tool_calls):
        return state

    # Return ONLY the new ToolMessages — the state reducer appends them.
    # Returning the full list would duplicate history and break the
    # tool_calls → ToolMessage pairing the model requires.
    new_tool_messages = []
    for tool_call in last_message.tool_calls:
        tool_name = tool_call.get("name", "")
        args = tool_call.get("args", {}) or {}
        execution = request_tool_execution(tool_name, args)

        if execution.status == "executed":
            content = f"[tool:{tool_name}] {execution.result}"
        elif execution.status == "denied":
            content = f"[tool:{tool_name}] DENIED: {execution.error}"
        elif execution.status == "failed":
            content = f"[tool:{tool_name}] FAILED: {execution.error}"
        else:
            content = (
                f"[tool:{tool_name}] This tool call requires human approval "
                f"(request {execution.id}). It has NOT been executed. "
                f"Tell the user a human operator must approve it in the operations workspace."
            )
        new_tool_messages.append(ToolMessage(content=content, tool_call_id=tool_call.get("id", "")))

    return {"messages": new_tool_messages}


def call_model(state: AgentState) -> dict:
    """Invoke the LLM with pipeline context, conversation history, and long-term memory."""
    base_prompt = state.get("system_prompt") or "You are an intelligent, critical-thinking AI assistant. Answer queries with high depth, natural reasoning, and clarity."
    intent = state.get("intent", "")
    pipeline_context = state.get("pipeline_context", "")
    answer_mode_directive = state.get("answer_mode_directive", "")

    RETRIEVAL_INTENTS = {"knowledge", "unknown", "memory"}

    if intent in RETRIEVAL_INTENTS and not pipeline_context:
        # STRICT KNOWLEDGE BASE BOUNDARY
        # When retrieval ran but 0 relevant documents matched, replace prompt sections completely
        # to eliminate conflicting directives asking for detailed/comprehensive answers.
        sections = [
            "You are a strict document-based AI assistant.",
            "\n=== STRICT KNOWLEDGE BASE BOUNDARY ===\n"
            "No relevant documents were found in the Knowledge Base for this query.\n"
            "State clearly and concisely in 1-2 short sentences that this topic is not covered in your Knowledge Base.\n"
            "Suggest uploading relevant documents or rephrasing the question.\n"
            "CRITICAL: DO NOT use general pre-training knowledge, world knowledge, or general memory under any circumstances. "
            "DO NOT provide any factual details about unmentioned entities."
        ]
    else:
        sections = [base_prompt]

        if answer_mode_directive:
            sections.append(f"\n--- Answer Mode ---\n{answer_mode_directive}")

        if intent:
            sections.append(f"\nRequest Type: {intent}")

        if pipeline_context:
            sections.append(f"\nRetrieved Knowledge:\n{pipeline_context}")
        else:
            # general / reasoning / coding / tool — bypass retrieval intentionally
            if intent == "reasoning":
                sections.append(
                    "\n=== REASONING & ANALYTICAL GUIDELINES ===\n"
                    "1. DO NOT GENERATE FORMULAIC COMPARISON TEMPLATES OR REPETITIVE NUMBERED SCHEMES "
                    "(e.g., '1. Nature of Subject, 2. Functionality, 3. Speed, 4. Training, 5. Outcome').\n"
                    "2. CATEGORY MISMATCHES: If comparing entities from different categories (e.g., a psychological framework like System 1 vs an individual athlete like Ronaldo):\n"
                    "   - Explicitly point out the category distinction in natural, conversational prose.\n"
                    "   - Do NOT force an artificial side-by-side comparative table.\n"
                    "   - Bridge the concepts fluidly (e.g., explain how fast, intuitive System 1 thinking enables split-second athletic execution on the pitch).\n"
                    "3. Write in articulate, insightful, fluid Markdown prose with natural paragraph transitions and meaningful subheadings."
                )
            else:
                sections.append(
                    "\n[Retrieval skipped for this request type — respond using natural reasoning.]\n"
                    "Think critically, be thorough, articulate, and avoid rigid templates."
                )
            # Strip KB directive to avoid confusing the model
            sections = [s for s in sections if "Answer Mode" not in s]

    # Long-term memory from Redis
    memories_str = ""
    try:
        r = redis.from_url(settings.REDIS_URL)
        memories = r.lrange("user:global:memories", 0, -1)
        if memories:
            memories_list = "\n".join([f"- {m.decode('utf-8')}" for m in memories])
            memories_str = (
                f"\nLong-Term Memory:\n"
                f"You have learned the following persistent facts about the user from previous sessions. "
                f"Use these to personalize your responses:\n{memories_list}"
            )
            sections.append(memories_str)
    except Exception as e:
        logger.error(f"Failed to fetch long-term memories: {e}")

    full_prompt = "\n".join(sections)

    safe_messages = [m for m in state["messages"] if type(m).__name__ != "SystemMessage"]
    for m in safe_messages:
        if isinstance(m.content, list):
            m.content = _strip_images(m.content)
    payload = [SystemMessage(content=full_prompt)] + safe_messages

    response = model_with_tools.invoke(payload)
    return {"messages": [response]}


workflow = StateGraph(AgentState)

workflow.add_node("agent", call_model)
workflow.add_node("action", action_node)

workflow.set_entry_point("agent")

workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "continue": "action",
        "end": END,
    },
)

workflow.add_edge("action", "agent")

graph = workflow.compile(checkpointer=checkpointer)

logger.info("LangGraph agent compiled with PostgreSQL checkpointer and pipeline context support ✓")
