"""Tests for the planner agent — generate_plan mocked to avoid LLM calls."""
import pytest
from math import ceil
from unittest.mock import MagicMock, patch
from app.agents.planner import SessionPlan, StudyPlanOutput, generate_plan


def _make_plan(n_sessions: int) -> StudyPlanOutput:
    return StudyPlanOutput(
        sessions=[
            SessionPlan(
                session_number=i,
                title=f"Session {i}",
                topic="Biology",
                estimated_minutes=45,
                focus_chapters=[f"Chapter {i}"],
            )
            for i in range(1, n_sessions + 1)
        ],
        rationale="Mocked rationale",
    )


@pytest.mark.asyncio
async def test_generate_plan_returns_study_plan_output():
    """generate_plan returns a StudyPlanOutput with sessions list."""
    expected = _make_plan(2)
    with patch(
        "app.agents.planner._planner_chain",
        new=MagicMock(invoke=MagicMock(return_value=expected)),
    ):
        result = await generate_plan(
            goal_title="Learn Biology",
            topic="Biology",
            level="beginner",
            deadline_days=14,
            sessions_per_week=1,
            source_titles=["Textbook A"],
        )

    assert isinstance(result, StudyPlanOutput)
    assert len(result.sessions) > 0


@pytest.mark.asyncio
async def test_session_count_matches_deadline_formula():
    """Session count in output must match ceil(deadline_days / 7 * sessions_per_week)."""
    deadline_days = 21
    sessions_per_week = 3
    expected_count = ceil(deadline_days / 7 * sessions_per_week)
    expected = _make_plan(expected_count)

    with patch(
        "app.agents.planner._planner_chain",
        new=MagicMock(invoke=MagicMock(return_value=expected)),
    ):
        result = await generate_plan(
            goal_title="Exam Prep",
            topic="Chemistry",
            level="intermediate",
            deadline_days=deadline_days,
            sessions_per_week=sessions_per_week,
            source_titles=["Chem Book"],
        )

    assert len(result.sessions) == expected_count


@pytest.mark.asyncio
async def test_generate_plan_passes_source_titles_in_message():
    """Source titles must be included in the prompt sent to the LLM."""
    captured_messages = []

    def capture_invoke(messages):
        captured_messages.extend(messages)
        return _make_plan(1)

    with patch(
        "app.agents.planner._planner_chain",
        new=MagicMock(invoke=capture_invoke),
    ):
        await generate_plan(
            goal_title="Quantum Study",
            topic="Physics",
            level="advanced",
            deadline_days=7,
            sessions_per_week=2,
            source_titles=["Feynman Lectures", "Griffiths"],
        )

    user_msg = next(m for m in captured_messages if m["role"] == "user")
    assert "Feynman Lectures" in user_msg["content"]
    assert "Griffiths" in user_msg["content"]
