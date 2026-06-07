"""
Integration tests for the Scholar API full surface.

LLM calls are mocked via unittest.mock.patch so tests run offline.
Uses FastAPI TestClient (sync) — no Docker runtime needed for test execution,
but tests should also pass inside the container via: docker compose exec backend pytest tests/
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app


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
        import aiosqlite, asyncio, uuid
        from app.config import settings

        source_id = str(uuid.uuid4())

        async def _insert_source():
            async with aiosqlite.connect(settings.sqlite_path) as db:
                await db.execute(
                    "INSERT OR IGNORE INTO knowledge_sources (id, title, source_type, status) VALUES (?, ?, ?, ?)",
                    (source_id, "Test Source", "pdf", "ready"),
                )
                await db.commit()

        asyncio.run(_insert_source())

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
        import aiosqlite, asyncio, uuid
        from app.config import settings

        source_id = str(uuid.uuid4())

        async def _insert_source():
            async with aiosqlite.connect(settings.sqlite_path) as db:
                await db.execute(
                    "INSERT OR IGNORE INTO knowledge_sources (id, title, source_type, status) VALUES (?, ?, ?, ?)",
                    (source_id, "Test Source for GET", "pdf", "ready"),
                )
                await db.commit()

        asyncio.run(_insert_source())

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
        import aiosqlite, asyncio, uuid
        from app.config import settings

        session_id = str(uuid.uuid4())
        goal_id = str(uuid.uuid4())

        async def _insert_session():
            async with aiosqlite.connect(settings.sqlite_path) as db:
                await db.execute(
                    "INSERT OR IGNORE INTO study_goals (id, title, topic, level, deadline_days, sessions_per_week, knowledge_source_ids, status) VALUES (?,?,?,?,?,?,?,?)",
                    (goal_id, "G", "T", "beginner", 7, 1, "[]", "active"),
                )
                await db.execute(
                    "INSERT OR IGNORE INTO study_sessions (id, goal_id, session_number, title, topic, estimated_minutes, status) VALUES (?,?,?,?,?,?,?)",
                    (session_id, goal_id, 1, "S1", "T", 45, "pending"),
                )
                await db.commit()

        asyncio.run(_insert_session())

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
        import aiosqlite, asyncio, uuid, json as _json
        from app.config import settings

        session_id = str(uuid.uuid4())
        goal_id = str(uuid.uuid4())

        # Pre-populate: goal + session with notes_markdown + stored quiz questions
        questions_data = [
            {"id": f"q{i}", "question": f"Q{i}?", "options": ["A", "B", "C", "D"],
             "correct_index": 0, "explanation": f"A is correct."}
            for i in range(1, 6)
        ]

        async def _setup():
            async with aiosqlite.connect(settings.sqlite_path) as db:
                await db.execute(
                    "INSERT OR IGNORE INTO study_goals (id, title, topic, level, deadline_days, sessions_per_week, knowledge_source_ids, status) VALUES (?,?,?,?,?,?,?,?)",
                    (goal_id, "G", "T", "beginner", 7, 1, "[]", "active"),
                )
                await db.execute(
                    "INSERT OR IGNORE INTO study_sessions (id, goal_id, session_number, title, topic, estimated_minutes, status, notes_markdown, quiz_questions) VALUES (?,?,?,?,?,?,?,?,?)",
                    (session_id, goal_id, 1, "S1", "T", 45, "in_progress",
                     "# Notes\n\nSome content.",
                     _json.dumps(questions_data)),
                )
                await db.commit()

        asyncio.run(_setup())

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
        async def _check_status():
            async with aiosqlite.connect(settings.sqlite_path) as db:
                async with db.execute(
                    "SELECT status, quiz_score FROM study_sessions WHERE id=?", (session_id,)
                ) as cur:
                    row = await cur.fetchone()
            return row

        import asyncio
        row = asyncio.run(_check_status())
        assert row is not None
        assert row[0] == "complete"
        assert row[1] == 1.0


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        """GET /health returns 200."""
        response = client.get("/health")
        assert response.status_code == 200
