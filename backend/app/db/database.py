import sqlite3
import aiosqlite
import psycopg2
from app.config import settings

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS knowledge_sources (
    id TEXT PRIMARY KEY, title TEXT, source_type TEXT,
    file_path TEXT, url TEXT, page_count INTEGER,
    pageindex_doc_id TEXT, status TEXT, created_at TEXT
);

CREATE TABLE IF NOT EXISTS study_goals (
    id TEXT PRIMARY KEY, title TEXT, topic TEXT,
    knowledge_source_ids TEXT, deadline_days INTEGER,
    level TEXT, sessions_per_week INTEGER, status TEXT, created_at TEXT
);

CREATE TABLE IF NOT EXISTS study_sessions (
    id TEXT PRIMARY KEY, goal_id TEXT, session_number INTEGER,
    title TEXT, topic TEXT, estimated_minutes INTEGER,
    status TEXT, quiz_score REAL, notes_markdown TEXT, created_at TEXT,
    FOREIGN KEY (goal_id) REFERENCES study_goals(id)
);

CREATE TABLE IF NOT EXISTS chat_history (
    id TEXT PRIMARY KEY, session_id TEXT, role TEXT,
    content TEXT, citations TEXT, created_at TEXT
);

CREATE TABLE IF NOT EXISTS quiz_questions (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    question TEXT NOT NULL,
    options TEXT NOT NULL,
    correct_index INTEGER NOT NULL,
    explanation TEXT NOT NULL,
    created_at TEXT,
    FOREIGN KEY (session_id) REFERENCES study_sessions(id)
);
"""

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


def init_db():
    """Initialize SQLite database with schema."""
    import os
    os.makedirs(os.path.dirname(settings.sqlite_path) or ".", exist_ok=True)
    conn = sqlite3.connect(settings.sqlite_path)
    conn.executescript(SQLITE_SCHEMA)
    conn.commit()
    # Add quiz_questions column if it doesn't exist (ALTER TABLE guard)
    try:
        conn.execute("ALTER TABLE study_sessions ADD COLUMN quiz_questions TEXT")
        conn.commit()
    except Exception:
        pass  # column already exists
    conn.close()


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


async def get_db():
    """Async context manager for SQLite connection."""
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row
        yield db
