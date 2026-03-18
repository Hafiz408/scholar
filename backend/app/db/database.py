import sqlite3
import aiosqlite
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


def init_db():
    """Initialize SQLite database with schema."""
    import os
    os.makedirs(os.path.dirname(settings.sqlite_path) or ".", exist_ok=True)
    conn = sqlite3.connect(settings.sqlite_path)
    conn.executescript(SQLITE_SCHEMA)
    conn.commit()
    conn.close()


async def get_db():
    """Async context manager for SQLite connection."""
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row
        yield db
