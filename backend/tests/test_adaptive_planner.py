"""
Tests for Phase 10: Adaptive Planner (ADP-01 through ADP-05).

All tests use monkeypatching for LLM calls. Database seeding uses the ORM
against the test Postgres instance (same DB the app uses).
"""
import uuid
import pytest
from unittest.mock import MagicMock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models.db_models import StudyGoal, StudySession


# ── Session factory helpers ───────────────────────────────────────────────────

def _make_session_factory():
    url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(url, poolclass=NullPool, echo=False)
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession), engine


async def _create_test_data():
    """Seed goal + 2 sessions for adaptive planner tests.

    Returns (goal_id, session1_id, session2_id).
    session1 is 'complete' (the target); session2 is 'pending' (downstream).
    """
    goal_id = str(uuid.uuid4())
    session1_id = str(uuid.uuid4())
    session2_id = str(uuid.uuid4())

    factory, engine = _make_session_factory()
    async with factory() as session:
        session.add(StudyGoal(
            id=goal_id,
            title="Biology Goal",
            topic="Cell Biology",
            level="beginner",
            knowledge_source_ids="[]",
            status="active",
            created_at="2026-01-01T00:00:00",
        ))
        session.add(StudySession(
            id=session1_id,
            goal_id=goal_id,
            session_number=1,
            title="Session 1: Cells",
            topic="Cell membrane",
            estimated_minutes=45,
            status="complete",
            created_at="2026-01-01T00:00:00",
        ))
        session.add(StudySession(
            id=session2_id,
            goal_id=goal_id,
            session_number=2,
            title="Session 2: DNA",
            topic="DNA replication",
            estimated_minutes=45,
            status="pending",
            created_at="2026-01-01T00:00:00",
        ))
        await session.commit()
    await engine.dispose()
    return goal_id, session1_id, session2_id


async def _set_quiz_score(session_id: str, score: float | None):
    factory, engine = _make_session_factory()
    async with factory() as session:
        obj = await session.get(StudySession, session_id)
        if obj is not None:
            obj.quiz_score = score
            await session.commit()
    await engine.dispose()


async def _get_session_number(session_id: str) -> int | None:
    factory, engine = _make_session_factory()
    async with factory() as session:
        obj = await session.get(StudySession, session_id)
        num = obj.session_number if obj else None
    await engine.dispose()
    return num


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_session_plan():
    """Return a SessionPlan instance for use as LLM mock output."""
    from app.agents.planner import SessionPlan

    return SessionPlan(
        title="Follow-up: Cells",
        topic="Cell membrane detail",
        estimated_minutes=35,
        focus_chapters=["Ch1"],
        session_number=0,  # will be overwritten by insert logic
    )


@pytest.fixture
def monkeypatched_chain(monkeypatch, mock_session_plan):
    """Patch _adaptive_chain.invoke to return mock_session_plan synchronously."""
    import app.agents.adaptive_planner as ap_mod

    mock_chain = MagicMock()
    mock_chain.invoke = MagicMock(return_value=mock_session_plan)
    monkeypatch.setattr(ap_mod, "_adaptive_chain", mock_chain)
    return mock_chain


# ── ADP-01: score < threshold triggers follow-up insertion ───────────────────

@pytest.mark.asyncio
async def test_score_below_threshold_inserts_followup(monkeypatched_chain):
    """ADP-01: quiz_score=0.50 (below 0.65) triggers follow-up insertion."""
    import app.agents.adaptive_planner as ap_mod

    goal_id, session1_id, session2_id = await _create_test_data()
    await _set_quiz_score(session1_id, 0.50)

    result = await ap_mod.handle_quiz_failure(session1_id)

    assert result["followup_session_added"] is True
    assert result["followup_session"] is not None
    assert result["followup_session"]["session_number"] == 2


@pytest.mark.asyncio
async def test_score_at_threshold_no_insertion(monkeypatched_chain):
    """ADP-01 boundary: quiz_score=0.65 (at threshold) does NOT trigger insertion."""
    import app.agents.adaptive_planner as ap_mod

    goal_id, session1_id, session2_id = await _create_test_data()
    await _set_quiz_score(session1_id, 0.65)

    result = await ap_mod.handle_quiz_failure(session1_id)

    assert result["followup_session_added"] is False
    assert result["followup_session"] is None


@pytest.mark.asyncio
async def test_null_score_no_insertion():
    """ADP-01: quiz_score=None (not yet scored) does NOT trigger insertion."""
    import app.agents.adaptive_planner as ap_mod

    goal_id, session1_id, session2_id = await _create_test_data()
    # quiz_score is already NULL — no update needed

    result = await ap_mod.handle_quiz_failure(session1_id)

    assert result["followup_session_added"] is False
    assert result["followup_session"] is None


# ── ADP-02: downstream session renumbering ───────────────────────────────────

@pytest.mark.asyncio
async def test_downstream_session_renumbered(monkeypatched_chain):
    """ADP-02: session2 (session_number=2) is shifted to 3 after follow-up insertion."""
    import app.agents.adaptive_planner as ap_mod

    goal_id, session1_id, session2_id = await _create_test_data()
    await _set_quiz_score(session1_id, 0.40)

    result = await ap_mod.handle_quiz_failure(session1_id)

    assert result["followup_session_added"] is True
    assert result["followup_session"]["session_number"] == 2

    # Verify session2 was renumbered from 2 to 3
    num = await _get_session_number(session2_id)
    assert num == 3


@pytest.mark.asyncio
async def test_completed_session_keeps_number(monkeypatched_chain):
    """ADP-02: session1 (the completed session) retains session_number=1 (not incremented)."""
    import app.agents.adaptive_planner as ap_mod

    goal_id, session1_id, session2_id = await _create_test_data()
    await _set_quiz_score(session1_id, 0.40)

    await ap_mod.handle_quiz_failure(session1_id)

    # session1 should still be at session_number=1
    num = await _get_session_number(session1_id)
    assert num == 1


# ── ADP-04: exception in planner propagates (router wraps it) ────────────────

@pytest.mark.asyncio
async def test_exception_propagates_from_planner(monkeypatch):
    """ADP-04: RuntimeError from _adaptive_chain.invoke is NOT swallowed by the planner."""
    import app.agents.adaptive_planner as ap_mod

    goal_id, session1_id, session2_id = await _create_test_data()
    await _set_quiz_score(session1_id, 0.40)

    # Make chain raise
    failing_chain = MagicMock()
    failing_chain.invoke = MagicMock(side_effect=RuntimeError("LLM unavailable"))
    monkeypatch.setattr(ap_mod, "_adaptive_chain", failing_chain)

    with pytest.raises(RuntimeError, match="LLM unavailable"):
        await ap_mod.handle_quiz_failure(session1_id)


# ── ADP-05: manual_adapt returns correct shape ───────────────────────────────

@pytest.mark.asyncio
async def test_manual_adapt_returns_shape(monkeypatched_chain):
    """ADP-05: POST /goals/{id}/adapt returns followup_sessions_added and followup_sessions."""
    import app.routers.goals as goals_mod

    goal_id, session1_id, session2_id = await _create_test_data()

    # Set session1 as failed (quiz_score < 0.65, status = complete)
    await _set_quiz_score(session1_id, 0.40)

    result = await goals_mod.manual_adapt(goal_id)

    assert "followup_sessions_added" in result
    assert isinstance(result["followup_sessions_added"], int)
    assert "followup_sessions" in result
    assert isinstance(result["followup_sessions"], list)
    assert result["followup_sessions_added"] == 1
    assert len(result["followup_sessions"]) == 1


@pytest.mark.asyncio
async def test_manual_adapt_no_failed_sessions():
    """ADP-05: Goal with no failed sessions returns followup_sessions_added=0 and empty list."""
    import app.routers.goals as goals_mod

    goal_id, session1_id, session2_id = await _create_test_data()
    # All sessions have quiz_score >= 0.65 or are pending — no failures

    result = await goals_mod.manual_adapt(goal_id)

    assert result == {"followup_sessions_added": 0, "followup_sessions": []}
