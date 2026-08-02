from langchain_core.tools import tool
from typing import Optional
from app.agent.tool_impls import (
    search_knowledge_base_impl,
    sm_integration_impl,
    remember_user_fact_impl,
)


@tool
def search_knowledge_base(query: str) -> str:
    """
    Searches the RAG knowledge base for information from uploaded documents.
    Use this tool whenever the user asks about specific custom documents or internal knowledge.
    """
    return search_knowledge_base_impl(query)


@tool
def sm_integration(action: str, target: str, content: Optional[str] = None) -> str:
    """
    Integrates with Social Media platforms.
    Actions: post, read, analyze. Target: platform name (twitter, linkedin, etc.)
    """
    return sm_integration_impl(action, target, content)


@tool
def remember_user_fact(fact: str) -> str:
    """
    Saves a persistent fact about the user (e.g., their name, preferences, background) into long-term memory.
    Use this tool whenever the user tells you something that you should remember across all future conversations.
    """
    return remember_user_fact_impl(fact)


# All tools available to the agent (web search disabled)
tools = [search_knowledge_base, sm_integration, remember_user_fact]
