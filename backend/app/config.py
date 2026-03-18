from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql://scholar:scholar_dev_password@db:5432/scholar"
    openai_api_key: str = ""
    langsmith_api_key: str = ""
    langchain_tracing_v2: bool = False
    langchain_project: str = "scholar"
    environment: str = "development"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
