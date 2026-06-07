import psycopg
import psycopg2
from app.config import settings

# Relational schema, ported from the previous SQLite schema to Postgres DDL.
# Type mapping: TEXT->TEXT, INTEGER->INTEGER, REAL->DOUBLE PRECISION.
# created_at columns are kept as TEXT (matching the prior SQLite behavior).
# Columns formerly added via ALTER TABLE are folded into the CREATE statements:
#   - study_goals.notion_page_url TEXT
#   - study_sessions.quiz_questions TEXT
PG_SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS knowledge_sources (
        id TEXT PRIMARY KEY, title TEXT, source_type TEXT,
        file_path TEXT, url TEXT, page_count INTEGER,
        pageindex_doc_id TEXT, status TEXT, created_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS study_goals (
        id TEXT PRIMARY KEY, title TEXT, topic TEXT,
        knowledge_source_ids TEXT, deadline_days INTEGER,
        level TEXT, sessions_per_week INTEGER, status TEXT, created_at TEXT,
        notion_page_url TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS study_sessions (
        id TEXT PRIMARY KEY, goal_id TEXT, session_number INTEGER,
        title TEXT, topic TEXT, estimated_minutes INTEGER,
        status TEXT, quiz_score DOUBLE PRECISION, notes_markdown TEXT, created_at TEXT,
        quiz_questions TEXT,
        FOREIGN KEY (goal_id) REFERENCES study_goals(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS chat_history (
        id TEXT PRIMARY KEY, session_id TEXT, role TEXT,
        content TEXT, citations TEXT, created_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS super_threads (
        thread_id TEXT PRIMARY KEY,
        title TEXT,
        message_count INTEGER DEFAULT 0,
        created_at TEXT,
        updated_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS quiz_questions (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        question TEXT NOT NULL,
        options TEXT NOT NULL,
        correct_index INTEGER NOT NULL,
        explanation TEXT NOT NULL,
        created_at TEXT,
        FOREIGN KEY (session_id) REFERENCES study_sessions(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cumulative_tests (
        id TEXT PRIMARY KEY,
        goal_id TEXT NOT NULL,
        questions TEXT NOT NULL,
        score DOUBLE PRECISION,
        weak_session_numbers TEXT,
        created_at TEXT,
        FOREIGN KEY (goal_id) REFERENCES study_goals(id)
    )
    """,
]


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
    """Initialize the Postgres database with the relational schema (sync psycopg3)."""
    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            # Ensure pgvector is available before any table that may reference it.
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            for stmt in PG_SCHEMA_STATEMENTS:
                cur.execute(stmt)
        conn.commit()


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
