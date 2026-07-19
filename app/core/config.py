from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "OwnGPT"
    DATABASE_URL: str
    REDIS_URL: str
    
    OPENAI_API_KEY: str
    TAVILY_API_KEY: str | None = None
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
