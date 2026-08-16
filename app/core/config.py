import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env into os.environ so all modules (including graph.py) can access it
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=_env_path, override=False)


def _default_sync_url(async_url: str) -> str:
    """Derive a psycopg (sync) URL from the asyncpg URL used by SQLAlchemy."""
    if async_url.startswith("postgresql+asyncpg://"):
        return async_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    return async_url


class Settings(BaseSettings):
    PROJECT_NAME: str = "OwnGPT"
    # Structured logging level for the JSON logging foundation (P2.1):
    # DEBUG | INFO | WARNING | ERROR. Applies at startup via setup_logging().
    LOG_LEVEL: str = "INFO"
    DATABASE_URL: str
    REDIS_URL: str

    # Sync engine URL (psycopg) for background threads (LangGraph pool/streaming).
    # Derived from DATABASE_URL when not set explicitly.
    SYNC_DATABASE_URL: str | None = None

    # OpenAI credentials — required ONLY when LLM_PROVIDER=openai. The
    # provider factory fails clearly at construction when they are missing;
    # provider=ollama never reads this key and never falls back to it.
    OPENAI_API_KEY: str = ""
    TAVILY_API_KEY: str | None = None

    # LLM provider — local development defaults to Ollama (no paid API).
    # "ollama" | "openai". There is NO automatic fallback between providers:
    # the configured provider is the only one ever constructed. If Ollama is
    # unreachable, requests fail clearly — OpenAI is never silently used.
    LLM_PROVIDER: str = "ollama"
    LLM_MODEL: str = "qwen3:8b"
    # In Docker Compose the OwnGPT container reaches Ollama via the service
    # name (http://ollama:11434). Host-based development overrides this in
    # .env to http://localhost:11434. Never localhost from the container.
    OLLAMA_BASE_URL: str = "http://ollama:11434"

    # LangSmith
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_TRACING_V2: bool = True
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGCHAIN_PROJECT: str = "ogpt"

    # PostgreSQL connection parameters for the psycopg connection pools
    # (LangGraph checkpointer, episodic loader). Environment-specific values
    # belong in .env / k8s configmaps — never hardcoded.
    PG_HOST: str = "db"
    PG_PORT: int = 5432
    PG_DB: str = "owngpt"
    PG_USER: str = "postgres"
    PG_PASSWORD: str = "postgres"

    # Model selection — server-side allowlist. The client may only pick
    # from these; everything else is rejected.
    SUPPORTED_MODELS: str = '["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"]'
    DEFAULT_MODEL: str = "gpt-4o-mini"
    TEMPERATURE_DEFAULT: float = 0.7
    TEMPERATURE_MIN: float = 0.0
    TEMPERATURE_MAX: float = 2.0

    # Authentication / ownership
    AUTH_TOKEN_EXPIRE_DAYS: int = 30
    # When enabled and exactly one user exists, requests without an
    # Authorization header are treated as that user. Keeps single-user
    # deployments working without a login page. OFF by default (secure for
    # multi-tenant); single-user deployments opt in via .env.
    AUTH_ALLOW_SINGLE_USER_FALLBACK: bool = False

    # Memory V2 — configuration-driven, deployment-pinned embeddings.
    # MEMORY_EMBEDDING_DIMENSION is consumed by both the model column and
    # migration m004. Changing it after deployment is an embedding re-index
    # migration (new migration number), NOT a config tweak.
    # Providers: "openai" | "none". The "ollama" branch exists in
    # build_embedding_provider and is unit-tested, but it produces 768-dim
    # vectors (nomic-embed-text) that are INCOMPATIBLE with the vector(1536)
    # memory schema — memory embeddings must remain "openai" or "none" until
    # a dimension migration is separately decided. Never set this to "ollama".
    MEMORY_EMBEDDING_PROVIDER: str = "openai"     # "openai" | "none"
    MEMORY_EMBEDDING_MODEL: str = "text-embedding-3-small"
    # Ollama embedding model (used by OllamaEmbeddingProvider only — never
    # by V2.1 memory, whose schema is pinned to MEMORY_EMBEDDING_DIMENSION).
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"
    MEMORY_EMBEDDING_DIMENSION: int = 1536
    MEMORY_EPISODIC_TTL_DAYS: int = 90
    MEMORY_CONFLICT_COSINE_THRESHOLD: float = 0.85
    MEMORY_RANK_W_COSINE: float = 0.6
    MEMORY_RANK_W_IMPORTANCE: float = 0.25
    MEMORY_RANK_W_RECENCY: float = 0.15
    MEMORY_RECENCY_HALF_LIFE_DAYS: float = 30.0
    MEMORY_EMBEDDING_BATCH_SIZE: int = 64
    MEMORY_ACCESS_UPDATE_THROTTLE_SECONDS: int = 3600

    # Memory V2.2 — routes agent recall through the governed MemoryService.
    # ON: retrieve_memory node recalls via MemoryService.search_memories;
    # OFF: no memory context is injected (legacy fallback window only).
    MEMORY_V2_GRAPH: bool = True

    # Memory extraction — execution control (P1 hardening).
    # Extraction runs on a bounded daemon worker pool; a Redis single-flight
    # claim (per conversation turn) and a distributed, TTL-protected throttle
    # coordinate across application workers. Redis is already a production
    # dependency (tracing, arq ingestion worker); every coordination failure
    # fails OPEN (chat is never affected) and falls back to in-process state.
    MEMORY_EXTRACTION_MAX_CONCURRENCY: int = 2     # concurrent extractions per worker process
    MEMORY_EXTRACTION_MAX_QUEUE: int = 200         # pending extractions per worker process
    MEMORY_EXTRACTION_SINGLE_FLIGHT_TTL_SECONDS: int = 300   # claim lifetime (crash safety net)
    MEMORY_EXTRACTION_TURN_INTERVAL: int = 3       # user turns between extractions, per session
    MEMORY_EXTRACTION_THROTTLE_TTL_SECONDS: int = 86400      # throttle marker lifetime

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def sync_database_url(self) -> str:
        return self.SYNC_DATABASE_URL or _default_sync_url(self.DATABASE_URL)


settings = Settings()