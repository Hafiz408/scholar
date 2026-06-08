from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime


# Knowledge Base
class KnowledgeSource(BaseModel):
    id: str
    title: str
    source_type: Literal["pdf", "url"]
    file_path: Optional[str] = None
    url: Optional[str] = None
    page_count: int
    pageindex_doc_id: Optional[str] = None  # None = vector-only fallback
    status: Literal["pending", "indexing_pageindex", "indexing_vectors", "ready", "failed"]
    created_at: datetime


class IngestionStatus(BaseModel):
    source_id: str
    status: str
    pages_processed: int
    total_pages: int
    error: Optional[str] = None


# Goals & Sessions
class StudyGoal(BaseModel):
    id: str
    title: str
    topic: str
    knowledge_source_ids: list[str]
    deadline_days: int
    level: Literal["beginner", "intermediate", "advanced"]
    sessions_per_week: int
    status: Literal["active", "complete"]
    created_at: datetime


class StudySession(BaseModel):
    id: str
    goal_id: str
    session_number: int
    title: str
    topic: str
    estimated_minutes: int
    status: Literal["pending", "in_progress", "complete"]
    quiz_score: Optional[float] = None  # 0.0–1.0, stored after quiz
    notes_markdown: Optional[str] = None
    created_at: datetime


class StudyPlan(BaseModel):
    goal: StudyGoal
    sessions: list[StudySession]
    total_sessions: int
    completed_sessions: int


# Retrieval
RetrievalStrategy = Literal["pageindex", "vector", "hybrid"]


class RetrievedChunk(BaseModel):
    source_id: str
    source_title: str
    content: str
    page_number: Optional[int] = None
    section_title: Optional[str] = None  # from PageIndex tree node title
    relevance_score: float
    retrieval_method: RetrievalStrategy


class RetrievalResult(BaseModel):
    chunks: list[RetrievedChunk]
    strategy_used: RetrievalStrategy
    latency_ms: int


# Chat & Quiz
class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    citations: list[RetrievedChunk] = []


class QuizQuestion(BaseModel):
    id: str
    question: str
    options: list[str]  # 4 MCQ options
    correct_index: int  # NOT sent to frontend during quiz
    explanation: str  # shown after submission


class QuizSubmission(BaseModel):
    session_id: str
    answers: dict[str, int]  # question_id → selected_index


class QuizResult(BaseModel):
    score: float
    total_questions: int
    correct_count: int
    per_question: list[dict]  # {question_id, correct, explanation}


# Goals & Super-Thread response models
class GoalSummary(BaseModel):
    # Descriptive/nullable columns are Optional so one legacy/partial row never
    # 500s the whole list (the computed counts are always present).
    id: str
    title: Optional[str] = None
    topic: Optional[str] = None
    level: Optional[str] = None
    status: Optional[str] = None
    created_at: Optional[datetime] = None
    deadline_days: Optional[int] = None
    total_sessions: int
    completed_sessions: int


class SuperThreadSummary(BaseModel):
    thread_id: str
    title: Optional[str] = None
    message_count: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SuperThreadMessage(BaseModel):
    role: str
    content: str


class SuperThreadDetail(BaseModel):
    thread_id: str
    title: Optional[str] = None
    messages: list[SuperThreadMessage]


# LangGraph State
class ScholarState(dict):
    """TypedDict-like state for LangGraph."""
    goal_id: str
    goal_title: str
    goal_topic: str
    knowledge_source_ids: list[str]
    level: str
    sessions: list[dict]
    current_session_index: int
    current_session_id: str
    current_topic: str
    notes_markdown: str
    chat_history: list[dict]
    quiz_questions: list[dict]
    quiz_score: Optional[float]
    retrieval_strategy: str
    messages: list
