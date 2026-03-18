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
"""

PGVECTOR_SCHEMA = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    source_title TEXT NOT NULL,
    page_number INTEGER,
    chunk_index INTEGER,
    content TEXT NOT NULL,
    embedding vector(1536),
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
    conn.close()


def init_pgvector_schema():
    """Initialize pgvector knowledge_chunks table and indexes in PostgreSQL."""
    conn = psycopg2.connect(settings.database_url)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(PGVECTOR_SCHEMA)
    conn.close()


async def get_db():
    """Async context manager for SQLite connection."""
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row
        yield db
