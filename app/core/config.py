import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env into os.environ so all modules (including graph.py) can access it
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=_env_path, override=False)


class Settings(BaseSettings):
    PROJECT_NAME: str = "OwnGPT"
    DATABASE_URL: str
    REDIS_URL: str
    
    OPENAI_API_KEY: str
    TAVILY_API_KEY: str | None = None
    
    # LangSmith
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_TRACING_V2: bool = True
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGCHAIN_PROJECT: str = "ogpt"

    PG_HOST: str = "db"
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
