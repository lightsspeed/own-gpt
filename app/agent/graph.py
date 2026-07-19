import logging
from psycopg_pool import ConnectionPool
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.prebuilt import ToolNode
from app.agent.state import AgentState
from app.agent.tools import tools
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, SystemMessage
from app.core.config import settings
import redis

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Database connection pool for the checkpointer
# Uses psycopg v3 (sync) – separate from the asyncpg pool used by SQLAlchemy
# ---------------------------------------------------------------------------
DB_CONNINFO = "host=db port=5432 dbname=owngpt user=postgres password=postgres"

pool = ConnectionPool(
    conninfo=DB_CONNINFO,
    max_size=20,
    kwargs={"autocommit": True, "prepare_threshold": 0},
)

# ---------------------------------------------------------------------------
# Checkpointer – persists full conversation state to PostgreSQL per thread_id
# ---------------------------------------------------------------------------
checkpointer = PostgresSaver(pool)
checkpointer.setup()   # creates langgraph checkpoint tables on first run

# ---------------------------------------------------------------------------
# LLM + Tools
# ---------------------------------------------------------------------------
model = ChatOpenAI(model="gpt-4o-mini", temperature=0)
model_with_tools = model.bind_tools(tools)

# ToolNode is the modern replacement for ToolExecutor in LangGraph >=0.1
tool_node = ToolNode(tools)


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------
def should_continue(state: AgentState) -> str:
    """Route to tool execution or end based on the last message."""
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "continue"
    return "end"


def call_model(state: AgentState) -> dict:
    """Invoke the LLM with the full conversation history and long-term memory."""
    memories_str = ""
    try:
        r = redis.from_url(settings.REDIS_URL)
        memories = r.lrange("user:global:memories", 0, -1)
        if memories:
            memories_list = "\n".join([f"- {m.decode('utf-8')}" for m in memories])
            memories_str = f"\n\n=== LONG-TERM MEMORY ===\nYou have learned the following persistent facts about the user from previous sessions. Use these to personalize your responses:\n{memories_list}"
    except Exception as e:
        logger.error(f"Failed to fetch long-term memories: {e}")
        
    base_prompt = state.get("system_prompt") or "You are a helpful AI assistant."
    full_prompt = f"{base_prompt}{memories_str}"
    
    # Filter out existing system messages so we don't accumulate them
    safe_messages = [m for m in state["messages"] if type(m).__name__ != "SystemMessage"]
    payload = [SystemMessage(content=full_prompt)] + safe_messages
    
    response = model_with_tools.invoke(payload)
    return {"messages": [response]}


# ---------------------------------------------------------------------------
# Build the LangGraph workflow
# ---------------------------------------------------------------------------
workflow = StateGraph(AgentState)

workflow.add_node("agent", call_model)
workflow.add_node("action", tool_node)   # ToolNode handles execution natively

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

# Compile with PostgreSQL checkpointer for persistent multi-turn memory
graph = workflow.compile(checkpointer=checkpointer)

logger.info("LangGraph agent compiled with PostgreSQL checkpointer ✓")
