from typing import Optional
from langchain_postgres.vectorstores import PGVector
from app.core.config import settings
from app.services.embeddings import build_kb_embeddings

# Since langchain_postgres PGVector requires a sync/async connection string:
# we will use psycopg3 connection string.
# settings.DATABASE_URL looks like: postgresql+asyncpg://postgres:postgres@db:5432/owngpt
# We need to change it to postgresql+psycopg:// for PGVector, or just postgresql://
connection_string = settings.DATABASE_URL.replace("+asyncpg", "+psycopg")

# Knowledge-base embeddings are configuration-driven via build_kb_embeddings()
# (defaults to Ollama nomic-embed-text). Decoupled from concrete Ollama class.
embeddings = build_kb_embeddings()

vector_store = PGVector(
    embeddings=embeddings,
    collection_name="own_gpt_docs",
    connection=connection_string,
    use_jsonb=True,
)

def add_documents_to_store(docs, ids: Optional[list[str]] = None):
    """
    Adds a list of LangChain Document objects to the pgvector store.
    Explicit UUIDs are passed to avoid null id constraint violations.
    """
    import uuid
    if ids is None:
        ids = [str(uuid.uuid4()) for _ in docs]
    vector_store.add_documents(docs, ids=ids)

def similarity_search(query: str, k: int = 4, filter: Optional[dict] = None, project_id: Optional[str] = None):
    """
    Searches the vector store for the most relevant documents.
    Supports optional PGVector metadata filtering and project_id scoping.
    """
    if project_id:
        proj_filter = {"project_id": project_id}
        if filter:
            filter = {"$and": [filter, proj_filter]}
        else:
            filter = proj_filter
    results = vector_store.similarity_search(query, k=k, filter=filter)
    return results

