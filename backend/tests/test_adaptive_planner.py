"""
Tests for Phase 10: Adaptive Planner (ADP-01 through ADP-05).

All tests use monkeypatching — no live LLM calls. All tests use a tmp_path
in-memory SQLite DB, never the real settings.sqlite_path.
"""
import asyncio
import pytest
import pytest_asyncio
import aiosqlite
from unittest.mock import MagicMock


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def tmp_db(tmp_path):
    """Create a temporary SQLite DB with minimal schema.

    Returns (db_path, goal_id, session1_id, session2_id).
    session1 is the "target" session; session2 is a downstream session.
    """
    import uuid

    db_path = str(tmp_path / "test.sqlite")
    goal_id = str(uuid.uuid4())
    session1_id = str(uuid.uuid4())
    session2_id = str(uuid.uuid4())

    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """CREATE TABLE study_goals (
                id TEXT PRIMARY KEY,
                title TEXT,
                topic TEXT,
                level TEXT DEFAULT 'beginner',
                knowledge_source_ids TEXT DEFAULT '[]'
            )"""
        )
        await db.execute(
            """CREATE TABLE study_sessions (
                id TEXT PRIMARY KEY,
                goal_id TEXT,
                session_number INTEGER,
                title TEXT,
                topic TEXT,
                estimated_minutes INTEGER DEFAULT 45,
                status TEXT DEFAULT 'pending',
                quiz_score REAL,
                created_at TEXT
            )"""
        )
        await db.execute(
            """CREATE TABLE knowledge_sources (
                id TEXT PRIMARY KEY,
                title TEXT
            )"""
        )
        await db.execute(
            "INSERT INTO study_goals (id, title, topic, level, knowledge_source_ids) VALUES (?, ?, ?, ?, ?)",
            (goal_id, "Biology Goal", "Cell Biology", "beginner", "[]"),
        )
        await db.execute(
            "INSERT INTO study_sessions (id, goal_id, session_number, title, topic, status) VALUES (?, ?, ?, ?, ?, ?)",
            (session1_id, goal_id, 1, "Session 1: Cells", "Cell membrane", "complete"),
        )
        await db.execute(
            "INSERT INTO study_sessions (id, goal_id, session_number, title, topic, status) VALUES (?, ?, ?, ?, ?, ?)",
            (session2_id, goal_id, 2, "Session 2: DNA", "DNA replication", "pending"),
        )
        await db.commit()

    return db_path, goal_id, session1_id, session2_id


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
async def test_score_below_threshold_inserts_followup(
    tmp_db, monkeypatched_chain, monkeypatch
):
    """ADP-01: quiz_score=0.50 (below 0.65) triggers follow-up insertion."""
    import app.agents.adaptive_planner as ap_mod

    db_path, goal_id, session1_id, session2_id = tmp_db

    # Set quiz_score to 0.50 in tmp DB
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE study_sessions SET quiz_score = ? WHERE id = ?",
            (0.50, session1_id),
        )
        await db.commit()

    # Redirect the module to use our tmp DB
    mock_settings = MagicMock()
    mock_settings.sqlite_path = db_path
    monkeypatch.setattr(ap_mod, "settings", mock_settings)

    result = await ap_mod.handle_quiz_failure(session1_id)

    assert result["followup_session_added"] is True
    assert result["followup_session"] is not None
    assert result["followup_session"]["session_number"] == 2


@pytest.mark.asyncio
async def test_score_at_threshold_no_insertion(
    tmp_db, monkeypatched_chain, monkeypatch
):
    """ADP-01 boundary: quiz_score=0.65 (at threshold) does NOT trigger insertion."""
    import app.agents.adaptive_planner as ap_mod

    db_path, goal_id, session1_id, session2_id = tmp_db

    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE study_sessions SET quiz_score = ? WHERE id = ?",
            (0.65, session1_id),
        )
        await db.commit()

    mock_settings = MagicMock()
    mock_settings.sqlite_path = db_path
    monkeypatch.setattr(ap_mod, "settings", mock_settings)

    result = await ap_mod.handle_quiz_failure(session1_id)

    assert result["followup_session_added"] is False
    assert result["followup_session"] is None


@pytest.mark.asyncio
async def test_null_score_no_insertion(tmp_db, monkeypatch):
    """ADP-01: quiz_score=None (not yet scored) does NOT trigger insertion."""
    import app.agents.adaptive_planner as ap_mod

    db_path, goal_id, session1_id, session2_id = tmp_db
    # quiz_score is already NULL by default — no update needed

    mock_settings = MagicMock()
    mock_settings.sqlite_path = db_path
    monkeypatch.setattr(ap_mod, "settings", mock_settings)

    result = await ap_mod.handle_quiz_failure(session1_id)

    assert result["followup_session_added"] is False
    assert result["followup_session"] is None


# ── ADP-02: downstream session renumbering ───────────────────────────────────

@pytest.mark.asyncio
async def test_downstream_session_renumbered(
    tmp_db, monkeypatched_chain, monkeypatch
):
    """ADP-02: session2 (session_number=2) is shifted to 3 after follow-up insertion."""
    import app.agents.adaptive_planner as ap_mod

    db_path, goal_id, session1_id, session2_id = tmp_db

    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE study_sessions SET quiz_score = ? WHERE id = ?",
            (0.40, session1_id),
        )
        await db.commit()

    mock_settings = MagicMock()
    mock_settings.sqlite_path = db_path
    monkeypatch.setattr(ap_mod, "settings", mock_settings)

    result = await ap_mod.handle_quiz_failure(session1_id)

    assert result["followup_session_added"] is True
    assert result["followup_session"]["session_number"] == 2

    # Verify session2 was renumbered from 2 to 3
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT session_number FROM study_sessions WHERE id = ?",
            (session2_id,),
        ) as cur:
            row = await cur.fetchone()
    assert row[0] == 3


@pytest.mark.asyncio
async def test_completed_session_keeps_number(
    tmp_db, monkeypatched_chain, monkeypatch
):
    """ADP-02: session1 (the completed session) retains session_number=1 (not incremented)."""
    import app.agents.adaptive_planner as ap_mod

    db_path, goal_id, session1_id, session2_id = tmp_db

    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE study_sessions SET quiz_score = ? WHERE id = ?",
            (0.40, session1_id),
        )
        await db.commit()

    mock_settings = MagicMock()
    mock_settings.sqlite_path = db_path
    monkeypatch.setattr(ap_mod, "settings", mock_settings)

    await ap_mod.handle_quiz_failure(session1_id)

    # session1 should still be at session_number=1
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT session_number FROM study_sessions WHERE id = ?",
            (session1_id,),
        ) as cur:
            row = await cur.fetchone()
    assert row[0] == 1


# ── ADP-04: exception in planner propagates (router wraps it) ────────────────

@pytest.mark.asyncio
async def test_exception_propagates_from_planner(tmp_db, monkeypatch):
    """ADP-04: RuntimeError from _adaptive_chain.invoke is NOT swallowed by the planner.

    The quiz router's try/except is the correct isolation point.
    """
    import app.agents.adaptive_planner as ap_mod

    db_path, goal_id, session1_id, session2_id = tmp_db

    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE study_sessions SET quiz_score = ? WHERE id = ?",
            (0.40, session1_id),
        )
        await db.commit()

    mock_settings = MagicMock()
    mock_settings.sqlite_path = db_path
    monkeypatch.setattr(ap_mod, "settings", mock_settings)

    # Make chain raise
    failing_chain = MagicMock()
    failing_chain.invoke = MagicMock(side_effect=RuntimeError("LLM unavailable"))
    monkeypatch.setattr(ap_mod, "_adaptive_chain", failing_chain)

    with pytest.raises(RuntimeError, match="LLM unavailable"):
        await ap_mod.handle_quiz_failure(session1_id)


# ── ADP-05: manual_adapt returns correct shape ───────────────────────────────

@pytest.mark.asyncio
async def test_manual_adapt_returns_shape(tmp_db, monkeypatched_chain, monkeypatch):
    """ADP-05: POST /goals/{id}/adapt returns followup_sessions_added and followup_sessions."""
    import app.agents.adaptive_planner as ap_mod
    import app.routers.goals as goals_mod

    db_path, goal_id, session1_id, session2_id = tmp_db

    # Set session1 as failed (quiz_score < 0.65, status = complete)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE study_sessions SET quiz_score = ?, status = ? WHERE id = ?",
            (0.40, "complete", session1_id),
        )
        await db.commit()

    mock_settings = MagicMock()
    mock_settings.sqlite_path = db_path
    monkeypatch.setattr(ap_mod, "settings", mock_settings)
    monkeypatch.setattr(goals_mod, "settings", mock_settings)

    result = await goals_mod.manual_adapt(goal_id)

    assert "followup_sessions_added" in result
    assert isinstance(result["followup_sessions_added"], int)
    assert "followup_sessions" in result
    assert isinstance(result["followup_sessions"], list)
    assert result["followup_sessions_added"] == 1
    assert len(result["followup_sessions"]) == 1


@pytest.mark.asyncio
async def test_manual_adapt_no_failed_sessions(tmp_db, monkeypatch):
    """ADP-05: Goal with no failed sessions returns followup_sessions_added=0 and empty list."""
    import app.routers.goals as goals_mod

    db_path, goal_id, session1_id, session2_id = tmp_db
    # All sessions have quiz_score >= 0.65 or are pending — no failures

    mock_settings = MagicMock()
    mock_settings.sqlite_path = db_path
    monkeypatch.setattr(goals_mod, "settings", mock_settings)

    result = await goals_mod.manual_adapt(goal_id)

    assert result == {"followup_sessions_added": 0, "followup_sessions": []}
