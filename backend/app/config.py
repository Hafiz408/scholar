from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql://scholar:scholar_dev_password@db:5432/scholar"
    openai_api_key: str = ""
    langsmith_api_key: str = ""
    langchain_tracing_v2: bool = False
    langchain_project: str = "scholar"
    environment: str = "development"
    pageindex_api_key: str = ""
    pageindex_base_url: str = "https://api.pageindex.ai"
    sqlite_path: str = "./data/scholar.db"
    upload_dir: str = "./data/uploads"
    max_upload_size_mb: int = 50
    llm_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
