"""SQLAlchemy 2.0 declarative ORM models for the Scholar Postgres schema.

These models mirror the raw DDL in ``app/core/db_schema.py`` EXACTLY — same table
names, column names, and types. This is the ORM foundation (phase O1); data-access
files are rewritten to use these models in a later phase. For now the ORM and the
raw ``app/core/pg.py`` shim coexist against the same tables.

Type mapping (matching the raw schema):
    TEXT             -> Text          (Mapped[str] / Mapped[str | None])
    INTEGER          -> Integer       (Mapped[int | None])
    DOUBLE PRECISION -> Float         (Mapped[float | None])
    vector(N)        -> Vector(N)     (pgvector)
    TIMESTAMP        -> DateTime      (knowledge_chunks.created_at only)

All ``created_at`` columns on the relational tables are kept as TEXT strings to
match the prior SQLite-derived behavior. ``knowledge_chunks.created_at`` is the
one exception — it is a real TIMESTAMP DEFAULT NOW() in the raw schema.
"""

from __future__ import annotations

import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, ForeignKey, Integer, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.config import settings


class Base(DeclarativeBase):
    """Single declarative base for all Scholar ORM models."""

    pass


class KnowledgeSource(Base):
    __tablename__ = "knowledge_sources"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pageindex_doc_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str | None] = mapped_column(Text, nullable=True)


class StudyGoal(Base):
    __tablename__ = "study_goals"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    knowledge_source_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    deadline_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    level: Mapped[str | None] = mapped_column(Text, nullable=True)
    sessions_per_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Folded in from a former ALTER TABLE.
    notion_page_url: Mapped[str | None] = mapped_column(Text, nullable=True)


class StudySession(Base):
    __tablename__ = "study_sessions"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    goal_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("study_goals.id"), nullable=True
    )
    session_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str | None] = mapped_column(Text, nullable=True)
    quiz_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Folded in from a former ALTER TABLE.
    quiz_questions: Mapped[str | None] = mapped_column(Text, nullable=True)


class ChatHistory(Base):
    __tablename__ = "chat_history"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    session_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    citations: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str | None] = mapped_column(Text, nullable=True)


class SuperThread(Base):
    __tablename__ = "super_threads"

    thread_id: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=0
    )
    created_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[str | None] = mapped_column(Text, nullable=True)


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        Text, ForeignKey("study_sessions.id"), nullable=False
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[str] = mapped_column(Text, nullable=False)
    correct_index: Mapped[int] = mapped_column(Integer, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str | None] = mapped_column(Text, nullable=True)


class CumulativeTest(Base):
    __tablename__ = "cumulative_tests"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    goal_id: Mapped[str] = mapped_column(
        Text, ForeignKey("study_goals.id"), nullable=False
    )
    questions: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    weak_session_numbers: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str | None] = mapped_column(Text, nullable=True)


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    source_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_title: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(settings.embedding_dimensions), nullable=True
    )
    # Unlike the relational tables, this is a real TIMESTAMP DEFAULT NOW().
    created_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime, nullable=True, server_default=func.now()
    )
