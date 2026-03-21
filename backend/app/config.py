from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql://scholar:scholar_dev_password@db:5432/scholar"
    openai_api_key: str = ""
    langsmith_api_key: str = ""
    langchain_tracing_v2: bool = False
    langchain_project: str = "scholar"
    environment: str = "development"
    sqlite_path: str = "./data/scholar.db"
    upload_dir: str = "./data/uploads"
    max_upload_size_mb: int = 50

    # LLM provider — one of: openai, openai-compat, anthropic, google
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_api_key: str = ""          # falls back to openai_api_key if empty
    llm_base_url: str = ""         # e.g. http://localhost:11434/v1 for Ollama

    # Embeddings — set EMBEDDING_BASE_URL to use any OpenAI-compatible embedding provider
    embedding_model: str = "text-embedding-3-small"
    embedding_api_key: str = ""    # falls back to openai_api_key if empty
    embedding_base_url: str = ""   # e.g. http://localhost:11434/v1 for Ollama
    embedding_dimensions: int = 1536  # must match the model (nomic-embed-text=768, etc.)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
