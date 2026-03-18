from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    pageindex_api_key: str = ""
    pageindex_base_url: str = "https://api.pageindex.ai"

    langchain_tracing_v2: bool = True
    langchain_api_key: str = ""
    langchain_project: str = "scholar-v1"

    postgres_url: str = "postgresql://scholar:scholar@localhost:5432/scholar"
    sqlite_path: str = "./data/scholar.db"
    upload_dir: str = "./data/uploads"
    max_upload_size_mb: int = 50

    allowed_origins: list[str] = ["http://localhost:3000"]

    class Config:
        env_file = ".env"


settings = Settings()
