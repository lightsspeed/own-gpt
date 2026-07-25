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

DB_CONNINFO = f"host={settings.PG_HOST} port=5432 dbname=owngpt user=postgres password=postgres"

pool = ConnectionPool(
    conninfo=DB_CONNINFO,
    max_size=20,
    kwargs={"autocommit": True, "prepare_threshold": 0},
)

checkpointer = PostgresSaver(pool)
checkpointer.setup()

model = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=settings.OPENAI_API_KEY)
model_with_tools = model.bind_tools(tools)

tool_node = ToolNode(tools)


def should_continue(state: AgentState) -> str:
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "continue"
    return "end"


def call_model(state: AgentState) -> dict:
    """Invoke the LLM with pipeline context, conversation history, and long-term memory."""
    base_prompt = state.get("system_prompt") or "You are a helpful AI assistant."
    intent = state.get("intent", "")
    pipeline_context = state.get("pipeline_context", "")

    # Build context sections
    sections = [base_prompt]

    if intent:
        sections.append(f"\nRequest Type: {intent}")

    if pipeline_context:
        sections.append(f"\nRetrieved Knowledge:\n{pipeline_context}")

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
    payload = [SystemMessage(content=full_prompt)] + safe_messages

    response = model_with_tools.invoke(payload)
    return {"messages": [response]}


workflow = StateGraph(AgentState)

workflow.add_node("agent", call_model)
workflow.add_node("action", tool_node)

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
