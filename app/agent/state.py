from typing import Annotated, Sequence, TypedDict
import operator
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    """The state of the agent."""
    messages: Annotated[Sequence[BaseMessage], operator.add]
    system_prompt: str
    answer_mode_directive: str
    intent: str
    rewritten_query: str
    pipeline_context: str
