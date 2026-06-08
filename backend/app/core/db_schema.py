import psycopg2
from app.config import settings


def _pgvector_schema(dimensions: int) -> str:
    return f"""
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    source_title TEXT NOT NULL,
    page_number INTEGER,
    chunk_index INTEGER,
    content TEXT NOT NULL,
    embedding vector({dimensions}),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chunks_embedding
    ON knowledge_chunks USING ivfflat (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_chunks_source
    ON knowledge_chunks (source_id);
"""


def _get_existing_chunk_dims(cur) -> int | None:
    """Return the vector dimension of the existing knowledge_chunks table, or None."""
    try:
        cur.execute(
            "SELECT format_type(atttypid, atttypmod) FROM pg_attribute "
            "WHERE attrelid = 'knowledge_chunks'::regclass AND attname = 'embedding' LIMIT 1"
        )
        row = cur.fetchone()
        if row and "(" in row[0]:
            return int(row[0].split("(")[1].rstrip(")"))
    except Exception:
        pass
    return None


def init_pgvector_schema():
    """Initialize pgvector knowledge_chunks table; recreates it if embedding dimensions changed."""
    conn = psycopg2.connect(settings.database_url)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        existing = _get_existing_chunk_dims(cur)
        if existing is not None and existing != settings.embedding_dimensions:
            import logging
            logging.getLogger(__name__).info(
                "Embedding dimensions changed %d→%d — recreating knowledge_chunks",
                existing, settings.embedding_dimensions,
            )
            cur.execute("DROP TABLE IF EXISTS knowledge_chunks CASCADE")
        cur.execute(_pgvector_schema(settings.embedding_dimensions))
    conn.close()


async def init_orm_models() -> None:
    """Ensure the pgvector extension and create all ORM-declared relational tables.

    ``Base.metadata.create_all`` is idempotent (creates only missing tables) and is
    the source of truth for the relational schema. ``init_pgvector_schema`` runs first
    (in the lifespan) to create ``knowledge_chunks`` with its ivfflat index.
    """
    from sqlalchemy import text
    from app.core.database import get_async_engine
    from app.models.db_models import Base

    engine = get_async_engine()
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
