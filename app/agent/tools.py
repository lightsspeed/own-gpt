from langchain_core.tools import tool
from typing import Optional
from app.services.vector_store import similarity_search
from app.core.config import settings


@tool
def search_knowledge_base(query: str) -> str:
    """
    Searches the RAG knowledge base for information from uploaded documents.
    Use this tool whenever the user asks about specific custom documents or internal knowledge.
    """
    try:
        results = similarity_search(query, k=3)
        if not results:
            return "No relevant information found in the knowledge base."
        context = "\n\n---\n\n".join([f"Source: {doc.metadata.get('filename', 'Unknown')}\n{doc.page_content}" for doc in results])
        return f"Found the following information:\n\n{context}"
    except Exception as e:
        return f"Error searching knowledge base: {str(e)}"



# @tool
# def search_web(query: str) -> str:
#     """Searches the web for current information, news, or real-time data."""
#     try:
#         from tavily import TavilyClient
#         client = TavilyClient(api_key=settings.TAVILY_API_KEY)
#         response = client.search(query=query, max_results=3)
#         results = response.get("results", [])
#         if not results:
#             return "No web results found."
#         formatted = "\n\n".join(
#             [f"**{r['title']}**\n{r['content']}\nSource: {r['url']}" for r in results]
#         )
#         return f"Web search results:\n\n{formatted}"
#     except Exception as e:
#         return f"Web search error: {str(e)}"


@tool
def sm_integration(action: str, target: str, content: Optional[str] = None) -> str:
    """
    Integrates with Social Media platforms.
    Actions: post, read, analyze. Target: platform name (twitter, linkedin, etc.)
    """
    return f"Mock SM Integration: {action} on {target} succeeded."


@tool
def remember_user_fact(fact: str) -> str:
    """
    Saves a persistent fact about the user (e.g., their name, preferences, background) into long-term memory.
    Use this tool whenever the user tells you something that you should remember across all future conversations.
    """
    try:
        import redis
        r = redis.from_url(settings.REDIS_URL)
        r.rpush("user:global:memories", fact)
        return f"Successfully saved fact to long-term memory: '{fact}'"
    except Exception as e:
        return f"Failed to save fact: {str(e)}"


# All tools available to the agent (web search disabled)
tools = [search_knowledge_base, sm_integration, remember_user_fact]

