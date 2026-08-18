from langchain_core.tools import tool
from typing import Optional
from app.agent.tool_impls import (
    search_knowledge_base_impl,
    web_search_impl,
    sm_integration_impl,
    remember_user_fact_impl,
    remember_session_fact_impl,
    forget_user_fact_impl,
)


@tool
def search_knowledge_base(query: str) -> str:
    """
    Searches the RAG knowledge base for information from uploaded documents.
    Use this tool whenever the user asks about specific custom documents or internal knowledge.
    """
    return search_knowledge_base_impl(query)


@tool
def web_search(query: str) -> str:
    """
    Searches the live web via Tavily API for real-time external information, news, or public web docs.
    Use this tool when the user asks about current events, external documentation, or topics not in internal knowledge.
    """
    return web_search_impl(query)


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


@tool
def remember_session_fact(fact: str) -> str:
    """
    Saves a fact about the current conversation (e.g., what was discussed, decided, or planned here)
    into conversation memory for THIS session only.
    Use this tool when the user says something that is only relevant to this conversation.
    """
    return remember_session_fact_impl(fact)


@tool
def forget_user_fact(fact: str) -> str:
    """
    Removes a previously saved memory fact (e.g., "my name is Alice") — from long-term
    memory first, or the current conversation if it was saved there.
    Use this tool when the user asks you to forget something you remember about them.
    """
    return forget_user_fact_impl(fact)


# All tools available to the agent (including Tavily live web search)
tools = [search_knowledge_base, web_search, sm_integration, remember_user_fact, remember_session_fact, forget_user_fact]

