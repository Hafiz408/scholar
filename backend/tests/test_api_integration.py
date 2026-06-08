"""
Integration tests for the Scholar API full surface.

LLM calls are mocked via unittest.mock.patch so tests run offline.
Uses FastAPI TestClient (sync) — no Docker runtime needed for test execution,
but tests should also pass inside the container via: docker compose exec backend pytest tests/
"""
import asyncio
import json
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

from app.config import settings
from app.main import app
from app.models.db_models import KnowledgeSource, StudyGoal, StudySession


# ---------------------------------------------------------------------------
# ORM seed helpers (replace the old aiosqlite helpers)
# ---------------------------------------------------------------------------

def _make_session_factory():
    """Fresh NullPool engine + sessionmaker — safe to use inside asyncio.run()."""
    url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(url, poolclass=NullPool, echo=False)
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession), engine


def _insert_source(source_id: str, title: str = "Test Source", source_type: str = "pdf") -> None:
    """Seed a knowledge_sources row via the ORM."""
    async def _run():
        factory, engine = _make_session_factory()
        async with factory() as session:
            # Use merge so INSERT OR IGNORE semantics apply (idempotent)
            existing = await session.get(KnowledgeSource, source_id)
            if existing is None:
                session.add(
                    KnowledgeSource(
                        id=source_id,
                        title=title,
                        source_type=source_type,
                        status="ready",
                    )
                )
                await session.commit()
        await engine.dispose()
    asyncio.run(_run())


def _insert_goal_and_session(
    goal_id: str,
    session_id: str,
    notes_markdown: str | None = None,
    quiz_questions: str | None = None,
    session_status: str = "pending",
) -> None:
    """Seed a study_goals + study_sessions row via the ORM."""
    async def _run():
        factory, engine = _make_session_factory()
        async with factory() as session:
            if await session.get(StudyGoal, goal_id) is None:
                session.add(
                    StudyGoal(
                        id=goal_id,
                        title="G",
                        topic="T",
                        level="beginner",
                        deadline_days=7,
                        sessions_per_week=1,
                        knowledge_source_ids="[]",
                        status="active",
                        created_at="2026-01-01T00:00:00",
                    )
                )
            if await session.get(StudySession, session_id) is None:
                session.add(
                    StudySession(
                        id=session_id,
                        goal_id=goal_id,
                        session_number=1,
                        title="S1",
                        topic="T",
                        estimated_minutes=45,
                        status=session_status,
                        notes_markdown=notes_markdown,
                        quiz_questions=quiz_questions,
                        created_at="2026-01-01T00:00:00",
                    )
                )
            await session.commit()
        await engine.dispose()
    asyncio.run(_run())


def _get_session_row(session_id: str) -> dict | None:
    """Read a study_sessions row from the DB via the ORM."""
    async def _run():
        factory, engine = _make_session_factory()
        async with factory() as session:
            obj = await session.get(StudySession, session_id)
            result = {"status": obj.status, "quiz_score": obj.quiz_score} if obj else None
        await engine.dispose()
        return result
    return asyncio.run(_run())


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    """Module-scoped TestClient — shares lifespan for all tests in this file."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def mock_planner():
    """Mock generate_plan to return a deterministic StudyPlanOutput without LLM."""
    from app.agents.planner import StudyPlanOutput, SessionPlan
    plan = StudyPlanOutput(
        sessions=[
            SessionPlan(
                session_number=1,
                title="Introduction",
                topic="Basics",
                estimated_minutes=45,
                focus_chapters=["Chapter 1"],
            )
        ],
        rationale="Mocked plan",
    )
    with patch(
        "app.agents.orchestrator.generate_plan",
        new=AsyncMock(return_value=plan),
    ):
        yield plan


@pytest.fixture
def mock_quiz_agent():
    """Mock generate_quiz to return 5 deterministic QuizQuestion objects without LLM."""
    from app.agents.quiz_agent import QuizQuestion
    questions = [
        QuizQuestion(
            id=f"q{i}",
            question=f"Question {i}?",
            options=["A", "B", "C", "D"],
            correct_index=0,
            explanation=f"A is correct for question {i}.",
        )
        for i in range(1, 6)
    ]
    with patch(
        "app.agents.quiz_agent._quiz_chain",
        new=MagicMock(invoke=MagicMock(return_value=MagicMock(questions=questions))),
    ):
        yield questions


# ---------------------------------------------------------------------------
# Helper: create a goal and return goal_id
# ---------------------------------------------------------------------------

def _create_goal_and_get_session(client, mock_planner, source_id: str):
    """POST /goals, return goal_id."""
    response = client.post(
        "/goals",
        json={
            "title": "Test Goal",
            "topic": "Biology",
            "level": "beginner",
            "deadline_days": 7,
            "sessions_per_week": 1,
            "source_ids": [source_id],
        },
    )
    assert response.status_code == 201, f"POST /goals failed: {response.text}"
    data = response.json()
    goal_id = data["goal_id"]
    return goal_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGoalsEndpoint:
    def test_create_goal_returns_201(self, client, mock_planner):
        """POST /goals with valid body returns 201 and a goal_id."""
        source_id = str(uuid.uuid4())
        _insert_source(source_id, title="Test Source")

        response = client.post(
            "/goals",
            json={
                "title": "Test Goal",
                "topic": "Biology",
                "level": "beginner",
                "deadline_days": 7,
                "sessions_per_week": 1,
                "source_ids": [source_id],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "goal_id" in data
        assert "session_count" in data
        assert data["session_count"] >= 1

    def test_get_goal_returns_plan(self, client, mock_planner):
        """GET /goals/{goal_id} returns 200 with goal data and a non-empty sessions list."""
        source_id = str(uuid.uuid4())
        _insert_source(source_id, title="Test Source for GET")

        # Create the goal first
        create_response = client.post(
            "/goals",
            json={
                "title": "GET Goal Test",
                "topic": "Chemistry",
                "level": "intermediate",
                "deadline_days": 7,
                "sessions_per_week": 1,
                "source_ids": [source_id],
            },
        )
        assert create_response.status_code == 201, f"POST /goals failed: {create_response.text}"
        goal_id = create_response.json()["goal_id"]

        # Now retrieve it
        response = client.get(f"/goals/{goal_id}")
        assert response.status_code == 200, f"GET /goals/{goal_id} failed: {response.text}"
        data = response.json()
        # Response shape: {"goal": {...}, "sessions": [...]}
        assert "goal" in data
        assert data["goal"]["id"] == goal_id
        assert "sessions" in data
        assert len(data["sessions"]) >= 1, "Expected at least one session in the plan"

    def test_create_goal_rejects_empty_source_ids(self, client):
        """POST /goals with no source_ids returns 422."""
        response = client.post(
            "/goals",
            json={
                "title": "No Sources",
                "topic": "Math",
                "level": "beginner",
                "deadline_days": 14,
                "sessions_per_week": 2,
                "source_ids": [],
            },
        )
        assert response.status_code == 422

    def test_get_goal_returns_404_for_unknown_id(self, client):
        """GET /goals/{id} returns 404 for a non-existent goal."""
        response = client.get("/goals/nonexistent-goal-id")
        assert response.status_code == 404


class TestSessionsEndpoint:
    def test_start_session_returns_404_for_unknown_session(self, client):
        """POST /sessions/{id}/start returns 404 for unknown session."""
        response = client.post(
            "/sessions/nonexistent-session-id/start",
            headers={"Accept": "text/event-stream"},
        )
        assert response.status_code == 404


class TestQuizEndpoint:
    def test_quiz_generate_returns_404_for_unknown_session(self, client):
        """POST /sessions/{id}/quiz/generate returns 404 for unknown session."""
        response = client.post("/sessions/nonexistent/quiz/generate")
        assert response.status_code == 404

    def test_quiz_generate_returns_422_when_notes_absent(self, client, mock_planner):
        """POST /sessions/{id}/quiz/generate returns 422 when session has no notes_markdown."""
        session_id = str(uuid.uuid4())
        goal_id = str(uuid.uuid4())
        _insert_goal_and_session(goal_id, session_id, notes_markdown=None)

        response = client.post(f"/sessions/{session_id}/quiz/generate")
        # notes_markdown is NULL -> 422 (no notes yet)
        assert response.status_code == 422

    def test_quiz_submit_returns_404_for_unknown_session(self, client):
        """POST /sessions/{id}/quiz/submit returns 404 for unknown session."""
        response = client.post(
            "/sessions/nonexistent/quiz/submit",
            json={"answers": {}},
        )
        assert response.status_code == 404

    def test_quiz_submit_scores_and_completes_session(self, client):
        """POST /sessions/{id}/quiz/submit returns QuizResult with score and marks session complete."""
        session_id = str(uuid.uuid4())
        goal_id = str(uuid.uuid4())

        # Pre-populate: goal + session with notes_markdown + stored quiz questions
        questions_data = [
            {"id": f"q{i}", "question": f"Q{i}?", "options": ["A", "B", "C", "D"],
             "correct_index": 0, "explanation": "A is correct."}
            for i in range(1, 6)
        ]

        _insert_goal_and_session(
            goal_id,
            session_id,
            notes_markdown="# Notes\n\nSome content.",
            quiz_questions=json.dumps(questions_data),
            session_status="in_progress",
        )

        # Submit all correct answers (correct_index=0 -> answer A for each)
        answers = {f"q{i}": 0 for i in range(1, 6)}
        response = client.post(
            f"/sessions/{session_id}/quiz/submit",
            json={"answers": answers},
        )
        assert response.status_code == 200, f"submit failed: {response.text}"
        result = response.json()
        assert result["score"] == 1.0
        assert result["correct_count"] == 5
        assert result["total_questions"] == 5
        assert len(result["per_question"]) == 5

        # Confirm session status updated to complete
        row = _get_session_row(session_id)
        assert row is not None
        assert row["status"] == "complete"
        assert row["quiz_score"] == 1.0


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        """GET /health returns 200."""
        response = client.get("/health")
        assert response.status_code == 200
