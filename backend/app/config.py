from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql://scholar:scholar_dev_password@db:5432/scholar"
    openai_api_key: str = ""
    langsmith_api_key: str = ""
    langchain_tracing_v2: bool = True
    langchain_project: str = "scholar-v2"
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

    # Vision ingestion — set VISION_MODEL to enable opt-in vision extraction
    vision_model: str = ""       # empty = vision disabled; e.g. "gpt-4o-mini"
    vision_max_pages: int = 20   # max pages per document to process; 0 = unlimited

    # Notion export — both required for export; empty = export disabled
    notion_api_key: str = ""         # Bearer token from Notion integration
    notion_parent_page_id: str = ""  # Notion page ID to create goal pages under

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
