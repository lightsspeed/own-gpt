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
    DATABASE_URL: str
    REDIS_URL: str

    # Sync engine URL (psycopg) for background threads (LangGraph pool/streaming).
    # Derived from DATABASE_URL when not set explicitly.
    SYNC_DATABASE_URL: str | None = None

    OPENAI_API_KEY: str
    TAVILY_API_KEY: str | None = None

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
    MEMORY_EMBEDDING_PROVIDER: str = "openai"     # "openai" | "none"
    MEMORY_EMBEDDING_MODEL: str = "text-embedding-3-small"
    MEMORY_EMBEDDING_DIMENSION: int = 1536
    MEMORY_EPISODIC_TTL_DAYS: int = 90
    MEMORY_CONFLICT_COSINE_THRESHOLD: float = 0.85
    MEMORY_RANK_W_COSINE: float = 0.6
    MEMORY_RANK_W_IMPORTANCE: float = 0.25
    MEMORY_RANK_W_RECENCY: float = 0.15
    MEMORY_RECENCY_HALF_LIFE_DAYS: float = 30.0
    MEMORY_EMBEDDING_BATCH_SIZE: int = 64
    MEMORY_ACCESS_UPDATE_THROTTLE_SECONDS: int = 3600

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def sync_database_url(self) -> str:
        return self.SYNC_DATABASE_URL or _default_sync_url(self.DATABASE_URL)


settings = Settings()