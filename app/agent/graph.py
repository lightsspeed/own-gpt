import logging
from psycopg_pool import ConnectionPool
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver
from app.agent.state import AgentState
from app.agent.tools import tools
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langchain_core.language_models import BaseChatModel
from app.core.config import settings
from app.core.llm_provider import build_llm
from app.core.model_config import DEFAULT_MODEL
from app.services.memory import search_memories as _search_memories
from app.services.embeddings import build_embedding_provider as _build_embedding_provider

logger = logging.getLogger(__name__)

MEMORY_TOOL_NAMES = frozenset({"remember_user_fact", "remember_session_fact", "forget_user_fact"})


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


# Connection parameters come from configuration (environment) — never
# hardcoded credentials. k8s/deployments override via PG_* env vars.
def _build_conninfo() -> str:
    return (
        f"host={settings.PG_HOST} port={settings.PG_PORT} "
        f"dbname={settings.PG_DB} user={settings.PG_USER} "
        f"password={settings.PG_PASSWORD}"
    )


DB_CONNINFO = _build_conninfo()

pool = ConnectionPool(
    conninfo=DB_CONNINFO,
    max_size=20,
    kwargs={"autocommit": True, "prepare_threshold": 0},
)

checkpointer = PostgresSaver(pool)


def setup_checkpointer() -> None:
    """Create LangGraph checkpoint tables. Deferred to app startup so a
    database outage at import time does not block the process."""
    checkpointer.setup()


def build_model(model_name: str, temperature: float) -> BaseChatModel:
    """Construct the agent LLM for a request. Model is server-validated by
    the API layer (allowlist) before reaching this point; the provider
    boundary (build_llm) resolves the configured LLM_PROVIDER."""
    return build_llm(model=model_name, temperature=temperature)


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
        # Session-scoped memory tools need the current conversation id, which
        # the model cannot know — inject it from the graph state. Memory tools
        # also receive the tenant identity so writes land in the owned scope.
        if tool_name in MEMORY_TOOL_NAMES:
            args = {
                **args,
                "session_id": args.get("session_id") or state.get("session_id", ""),
                "user_id": state.get("user_id", ""),
                "project_id": state.get("project_id") or "",
            }
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
    answer_mode = state.get("answer_mode", "")

    # Memory recalls skip retrieval by design — they must never hit the
    # knowledge-base boundary; they are answered from the memory sections below.
    RETRIEVAL_INTENTS = {"knowledge", "unknown", "coding", "reasoning"}

    if (answer_mode == "no_evidence" and not pipeline_context) or (
        intent in RETRIEVAL_INTENTS and not pipeline_context
    ):
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

    # Long-term memory computed by the retrieve_memory node (V2.1 store).
    memory_context = state.get("memory_context", "")
    if memory_context:
        sections.append("\n" + memory_context)

    full_prompt = "\n".join(sections)

    safe_messages = [m for m in state["messages"] if type(m).__name__ != "SystemMessage"]
    for m in safe_messages:
        if isinstance(m.content, list):
            m.content = _strip_images(m.content)
    payload = [SystemMessage(content=full_prompt)] + safe_messages

    # Per-request model selection — the model field flows through the graph
    # state from the validated request; never a module-level hardcode.
    model_name = state.get("model") or DEFAULT_MODEL
    temperature = state.get("temperature")
    if temperature is None:
        temperature = 0.4
    model_with_tools = build_model(model_name, temperature).bind_tools(tools)

    response = model_with_tools.invoke(payload)
    return {"messages": [response]}


def retrieve_memory(state: AgentState) -> dict:
    """Recall cross-session context from the governed V2.1 memory store.

    Runs before the first model call. Produces `memory_context` (a text block
    appended to the system prompt by call_model) from MemoryService-ranked
    active memories in the project scope plus user-wide scope. Never raises:
    any failure degrades to no memory context — memory is context, not truth.
    """
    if not settings.MEMORY_V2_GRAPH:
        return {"memory_context": ""}

    user_id = state.get("user_id", "")
    project_id = state.get("project_id") or None
    query_text = ""
    for m in reversed(state.get("messages", [])):
        if type(m).__name__ == "HumanMessage":
            query_text = _strip_images(m.content)
            break
    if not user_id or not query_text.strip():
        return {"memory_context": ""}

    try:
        from app.core.database import SyncSessionLocal

        provider = _build_embedding_provider()
        with SyncSessionLocal() as db:
            hits = _search_memories(
                db,
                user_id=user_id,
                query=query_text,
                project_id=project_id,
                k=5,
                max_tokens=400,
                embed=provider.embed if provider else None,
            )
    except Exception as e:
        logger.error("memory_recall_failed user=%s error=%s", user_id, e)
        return {"memory_context": ""}

    if not hits:
        return {"memory_context": ""}
    facts_list = "\n".join(f"- {hit.entity.statement}" for hit in hits)
    return {
        "memory_context": (
            "Long-Term Memory:\n"
            "You have learned the following persistent facts about the user from previous sessions. "
            "Use these to personalize your responses:\n"
            f"{facts_list}"
        )
    }


workflow = StateGraph(AgentState)

workflow.add_node("retrieve_memory", retrieve_memory)
workflow.add_node("agent", call_model)
workflow.add_node("action", action_node)

workflow.set_entry_point("retrieve_memory")

workflow.add_edge("retrieve_memory", "agent")

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