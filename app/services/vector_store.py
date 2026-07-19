from langchain_openai import OpenAIEmbeddings
from langchain_postgres.vectorstores import PGVector
from app.core.config import settings

# Since langchain_postgres PGVector requires a sync/async connection string:
# we will use psycopg3 connection string.
# settings.DATABASE_URL looks like: postgresql+asyncpg://postgres:postgres@db:5432/owngpt
# We need to change it to postgresql+psycopg:// for PGVector, or just postgresql://
connection_string = settings.DATABASE_URL.replace("+asyncpg", "+psycopg")

embeddings = OpenAIEmbeddings(api_key=settings.OPENAI_API_KEY)

vector_store = PGVector(
    embeddings=embeddings,
    collection_name="own_gpt_docs",
    connection=connection_string,
    use_jsonb=True,
)

def add_documents_to_store(docs):
    """
    Adds a list of LangChain Document objects to the pgvector store.
    Explicit UUIDs are passed to avoid null id constraint violations.
    """
    import uuid
    ids = [str(uuid.uuid4()) for _ in docs]
    vector_store.add_documents(docs, ids=ids)

def similarity_search(query: str, k: int = 4):
    """
    Searches the vector store for the most relevant documents.
    """
    results = vector_store.similarity_search(query, k=k)
    return results
