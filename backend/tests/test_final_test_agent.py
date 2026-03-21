"""
Tests for Phase 11: Final Test Agent + Orchestrator V2.

All tests use monkeypatching — no live LLM calls. All tests use a tmp_path
in-memory SQLite DB, never the real settings.sqlite_path.

Coverage:
    TST-01 / TST-02  — generate_test() tags session_number; caps at MAX_TEST_QUESTIONS
    TST-03           — init_db() creates cumulative_tests table (idempotent)
    TST-04           — generate_final_test() returns 400 for incomplete/no sessions
    TST-05           — submit_final_test() marks goal complete when score >= 0.70
    TST-06           — submit_final_test() returns weak_session_numbers
    ORC-01           — ScholarState TypedDict has V2 annotations
    ORC-02           — update_goal_progress() returns correct shape
"""
import asyncio
import json
import sqlite3
import uuid

import aiosqlite
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

# ── Fixtures ─────────────────────────────────────────────────────────────────

SQLITE_SCHEMA_MINIMAL = """
CREATE TABLE IF NOT EXISTS study_goals (
    id TEXT PRIMARY KEY,
    title TEXT,
    topic TEXT,
    knowledge_source_ids TEXT DEFAULT '[]',
    deadline_days INTEGER,
    level TEXT DEFAULT 'beginner',
    sessions_per_week INTEGER,
    status TEXT DEFAULT 'active',
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS study_sessions (
    id TEXT PRIMARY KEY,
    goal_id TEXT,
    session_number INTEGER,
    title TEXT,
    topic TEXT,
    estimated_minutes INTEGER DEFAULT 45,
    status TEXT DEFAULT 'pending',
    quiz_score REAL,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS cumulative_tests (
    id TEXT PRIMARY KEY,
    goal_id TEXT NOT NULL,
    questions TEXT NOT NULL,
    score REAL,
    weak_session_numbers TEXT,
    created_at TEXT
);
"""


@pytest_asyncio.fixture
async def tmp_db(tmp_path):
    """Create a temporary SQLite DB with minimal schema.

    Seeds: one goal (status='active') + two complete sessions.
    Returns (db_path, goal_id, session1_id, session2_id).
    """
    db_path = str(tmp_path / "test.sqlite")
    goal_id = str(uuid.uuid4())
    session1_id = str(uuid.uuid4())
    session2_id = str(uuid.uuid4())

    async with aiosqlite.connect(db_path) as db:
        await db.executescript(SQLITE_SCHEMA_MINIMAL)
        await db.execute(
            "INSERT INTO study_goals (id, title, topic, knowledge_source_ids, status) VALUES (?, ?, ?, ?, ?)",
            (goal_id, "Biology Goal", "Cell Biology", "[]", "active"),
        )
        await db.execute(
            "INSERT INTO study_sessions (id, goal_id, session_number, title, topic, status) VALUES (?, ?, ?, ?, ?, ?)",
            (session1_id, goal_id, 1, "Session 1: Cells", "Cells", "complete"),
        )
        await db.execute(
            "INSERT INTO study_sessions (id, goal_id, session_number, title, topic, status) VALUES (?, ?, ?, ?, ?, ?)",
            (session2_id, goal_id, 2, "Session 2: DNA", "DNA", "complete"),
        )
        await db.commit()

    return db_path, goal_id, session1_id, session2_id


@pytest.fixture
def mock_test_output():
    """Return a TestOutput with 2 TestQuestion objects (one per session)."""
    from app.agents.test_agent import TestOutput, TestQuestion

    q1 = TestQuestion(
        id=str(uuid.uuid4()),
        session_number=1,
        question="What is a cell?",
        options=["A membrane", "A basic unit of life", "A molecule", "An atom"],
        correct_index=1,
        explanation="Cells are the basic units of life.",
    )
    q2 = TestQuestion(
        id=str(uuid.uuid4()),
        session_number=2,
        question="What does DNA stand for?",
        options=["Deoxyribonucleic Acid", "Ribose Acid", "Amino Acid", "Fatty Acid"],
        correct_index=0,
        explanation="DNA stands for Deoxyribonucleic Acid.",
    )
    return TestOutput(questions=[q1, q2])


@pytest.fixture
def monkeypatched_chain(monkeypatch, mock_test_output):
    """Patch _test_chain.invoke to return mock_test_output synchronously."""
    import app.agents.test_agent as ta_mod

    mock_chain = MagicMock()
    mock_chain.invoke = MagicMock(return_value=mock_test_output)
    monkeypatch.setattr(ta_mod, "_test_chain", mock_chain)
    return mock_chain


@pytest.fixture
def mock_retrieve(monkeypatch):
    """Patch retrieve in test_agent to return a mock result with .chunks."""
    import app.agents.test_agent as ta_mod

    mock_chunk = MagicMock()
    mock_chunk.content = "Cells are the building blocks of life."
    mock_result = MagicMock()
    mock_result.chunks = [mock_chunk]

    async def mock_retrieve_fn(query, source_ids, top_k=3):
        return mock_result

    monkeypatch.setattr(ta_mod, "retrieve", mock_retrieve_fn)
    return mock_retrieve_fn


# ── TST-01 / TST-02: session_number tagging and MAX_TEST_QUESTIONS cap ────────

@pytest.mark.asyncio
async def test_generate_test_tags_session_numbers(monkeypatch, mock_retrieve):
    """TST-01/TST-02: generate_test() enforces session_number post-LLM on every question.

    The mock chain returns fresh questions per call (via side_effect factory). With 2
    sessions we get 4 total. Even if LLM returns the wrong session_number, the loop
    enforces the correct value.
    """
    import app.agents.test_agent as ta_mod
    from app.agents.test_agent import TestOutput, TestQuestion, generate_test

    def make_output(session_number_from_llm: int) -> TestOutput:
        """Return fresh TestOutput with WRONG session_number to prove enforcement."""
        return TestOutput(questions=[
            TestQuestion(
                id=str(uuid.uuid4()),
                session_number=99,  # deliberately wrong — loop must overwrite this
                question=f"Q1 sn={session_number_from_llm}?",
                options=["A", "B", "C", "D"],
                correct_index=0,
                explanation="Explanation.",
            ),
            TestQuestion(
                id=str(uuid.uuid4()),
                session_number=99,  # deliberately wrong
                question=f"Q2 sn={session_number_from_llm}?",
                options=["A", "B", "C", "D"],
                correct_index=1,
                explanation="Explanation.",
            ),
        ])

    call_count = [0]

    def invoke_side_effect(messages):
        call_count[0] += 1
        return make_output(call_count[0])

    mock_chain = MagicMock()
    mock_chain.invoke = MagicMock(side_effect=invoke_side_effect)
    monkeypatch.setattr(ta_mod, "_test_chain", mock_chain)

    sessions = [
        {"session_number": 1, "topic": "Cells"},
        {"session_number": 2, "topic": "DNA"},
    ]
    questions = await generate_test(sessions=sessions, source_ids=[])

    # 2 sessions × 2 questions each = 4 (under MAX_TEST_QUESTIONS=15)
    assert len(questions) == 4
    # session_number is enforced post-LLM; first 2 from session 1, next 2 from session 2
    assert questions[0].session_number == 1
    assert questions[1].session_number == 1
    assert questions[2].session_number == 2
    assert questions[3].session_number == 2


@pytest.mark.asyncio
async def test_generate_test_caps_at_15_questions(monkeypatch, mock_retrieve):
    """TST-01: with 8 sessions returning 2 questions each, result is capped at 15."""
    import app.agents.test_agent as ta_mod
    from app.agents.test_agent import TestOutput, TestQuestion, generate_test

    # Each LLM call returns 2 questions
    def make_output_for_session(session_number: int) -> TestOutput:
        return TestOutput(
            questions=[
                TestQuestion(
                    id=str(uuid.uuid4()),
                    session_number=session_number,
                    question=f"Q1 for session {session_number}?",
                    options=["A", "B", "C", "D"],
                    correct_index=0,
                    explanation="Explanation.",
                ),
                TestQuestion(
                    id=str(uuid.uuid4()),
                    session_number=session_number,
                    question=f"Q2 for session {session_number}?",
                    options=["A", "B", "C", "D"],
                    correct_index=1,
                    explanation="Explanation.",
                ),
            ]
        )

    call_count = [0]

    def mock_invoke(messages):
        # determine session_number from call_count
        sn = call_count[0] + 1
        call_count[0] += 1
        return make_output_for_session(sn)

    mock_chain = MagicMock()
    mock_chain.invoke = MagicMock(side_effect=mock_invoke)
    monkeypatch.setattr(ta_mod, "_test_chain", mock_chain)

    sessions = [{"session_number": i, "topic": f"Topic {i}"} for i in range(1, 9)]
    questions = await generate_test(sessions=sessions, source_ids=[])

    assert len(questions) <= ta_mod.MAX_TEST_QUESTIONS
    assert len(questions) == 15


# ── TST-03: init_db() creates cumulative_tests table ─────────────────────────

def test_init_db_creates_cumulative_tests_table(tmp_path, monkeypatch):
    """TST-03: fresh DB after init_db() has cumulative_tests table."""
    from app.db import database as db_mod

    db_path = str(tmp_path / "fresh.sqlite")
    mock_settings = MagicMock()
    mock_settings.sqlite_path = db_path
    monkeypatch.setattr(db_mod, "settings", mock_settings)

    db_mod.init_db()

    conn = sqlite3.connect(db_path)
    # Should not raise — table exists
    conn.execute("SELECT 1 FROM cumulative_tests LIMIT 0")
    conn.close()


def test_init_db_idempotent(tmp_path, monkeypatch):
    """TST-03: calling init_db() twice on the same DB raises no error."""
    from app.db import database as db_mod

    db_path = str(tmp_path / "idempotent.sqlite")
    mock_settings = MagicMock()
    mock_settings.sqlite_path = db_path
    monkeypatch.setattr(db_mod, "settings", mock_settings)

    db_mod.init_db()
    db_mod.init_db()  # second call — must not raise

    conn = sqlite3.connect(db_path)
    conn.execute("SELECT 1 FROM cumulative_tests LIMIT 0")
    conn.close()


# ── TST-04: generate_final_test returns 400 for bad goal state ────────────────

@pytest.mark.asyncio
async def test_generate_endpoint_400_when_sessions_incomplete(
    tmp_db, monkeypatched_chain, mock_retrieve, monkeypatch
):
    """TST-04: goal with a pending session returns 400."""
    import app.routers.test as router_mod
    from fastapi import HTTPException

    db_path, goal_id, session1_id, session2_id = tmp_db

    # Make session2 pending
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE study_sessions SET status='pending' WHERE id=?", (session2_id,)
        )
        await db.commit()

    mock_settings = MagicMock()
    mock_settings.sqlite_path = db_path
    monkeypatch.setattr(router_mod, "settings", mock_settings)

    with pytest.raises(HTTPException) as exc_info:
        await router_mod.generate_final_test(goal_id)

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_generate_endpoint_400_when_no_sessions(tmp_path, monkeypatch):
    """TST-04: goal with no sessions returns 400."""
    import app.routers.test as router_mod
    from fastapi import HTTPException

    db_path = str(tmp_path / "nosessions.sqlite")
    goal_id = str(uuid.uuid4())

    async with aiosqlite.connect(db_path) as db:
        await db.executescript(SQLITE_SCHEMA_MINIMAL)
        await db.execute(
            "INSERT INTO study_goals (id, title, topic, knowledge_source_ids, status) VALUES (?, ?, ?, ?, ?)",
            (goal_id, "Empty Goal", "Nothing", "[]", "active"),
        )
        await db.commit()

    mock_settings = MagicMock()
    mock_settings.sqlite_path = db_path
    monkeypatch.setattr(router_mod, "settings", mock_settings)

    with pytest.raises(HTTPException) as exc_info:
        await router_mod.generate_final_test(goal_id)

    assert exc_info.value.status_code == 400


# ── TST-05: submit_final_test marks goal complete at score >= 0.70 ─────────────

def _build_questions_json(q1_id: str, q2_id: str) -> str:
    """Helper: build JSON for 2 questions — q1 correct_index=0, q2 correct_index=1."""
    return json.dumps([
        {
            "id": q1_id,
            "session_number": 1,
            "question": "Q1?",
            "options": ["A", "B", "C", "D"],
            "correct_index": 0,
            "explanation": "Correct is A.",
        },
        {
            "id": q2_id,
            "session_number": 2,
            "question": "Q2?",
            "options": ["A", "B", "C", "D"],
            "correct_index": 1,
            "explanation": "Correct is B.",
        },
    ])


async def _seed_test(db_path: str, goal_id: str) -> tuple[str, str, str]:
    """Seed a cumulative_test row and return (test_id, q1_id, q2_id)."""
    q1_id = str(uuid.uuid4())
    q2_id = str(uuid.uuid4())
    test_id = str(uuid.uuid4())
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO cumulative_tests (id, goal_id, questions, created_at) VALUES (?, ?, ?, datetime('now'))",
            (test_id, goal_id, _build_questions_json(q1_id, q2_id)),
        )
        await db.commit()
    return test_id, q1_id, q2_id


@pytest.mark.asyncio
async def test_submit_marks_goal_complete_on_passing_score(tmp_db, monkeypatch):
    """TST-05: score=1.0 (all correct) marks goal.status='complete'."""
    import app.routers.test as router_mod
    from app.routers.test import TestSubmitRequest

    db_path, goal_id, session1_id, session2_id = tmp_db
    test_id, q1_id, q2_id = await _seed_test(db_path, goal_id)

    mock_settings = MagicMock()
    mock_settings.sqlite_path = db_path
    monkeypatch.setattr(router_mod, "settings", mock_settings)

    # Both correct
    body = TestSubmitRequest(answers={q1_id: 0, q2_id: 1})
    result = await router_mod.submit_final_test(goal_id, body)

    assert result["score"] == 1.0
    assert result["goal_complete"] is True

    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT status FROM study_goals WHERE id=?", (goal_id,)) as cur:
            row = await cur.fetchone()
    assert row[0] == "complete"


@pytest.mark.asyncio
async def test_submit_does_not_mark_complete_on_fail(tmp_db, monkeypatch):
    """TST-05: score=0.0 (all wrong) — goal.status stays 'active'."""
    import app.routers.test as router_mod
    from app.routers.test import TestSubmitRequest

    db_path, goal_id, session1_id, session2_id = tmp_db
    test_id, q1_id, q2_id = await _seed_test(db_path, goal_id)

    mock_settings = MagicMock()
    mock_settings.sqlite_path = db_path
    monkeypatch.setattr(router_mod, "settings", mock_settings)

    # Both wrong (selecting wrong index)
    body = TestSubmitRequest(answers={q1_id: 3, q2_id: 3})
    result = await router_mod.submit_final_test(goal_id, body)

    assert result["score"] == 0.0
    assert result["goal_complete"] is False

    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT status FROM study_goals WHERE id=?", (goal_id,)) as cur:
            row = await cur.fetchone()
    assert row[0] == "active"


@pytest.mark.asyncio
async def test_submit_exactly_70_percent_marks_complete(tmp_path, monkeypatch):
    """TST-05: exactly 70% correct (7/10) marks goal complete."""
    import app.routers.test as router_mod
    from app.routers.test import TestSubmitRequest

    db_path = str(tmp_path / "threshold.sqlite")
    goal_id = str(uuid.uuid4())

    # Create 10 questions, all in session 1
    question_ids = [str(uuid.uuid4()) for _ in range(10)]
    questions_data = [
        {
            "id": qid,
            "session_number": 1,
            "question": f"Q{i}?",
            "options": ["A", "B", "C", "D"],
            "correct_index": 0,  # correct answer is always index 0
            "explanation": "A is correct.",
        }
        for i, qid in enumerate(question_ids)
    ]

    test_id = str(uuid.uuid4())

    async with aiosqlite.connect(db_path) as db:
        await db.executescript(SQLITE_SCHEMA_MINIMAL)
        await db.execute(
            "INSERT INTO study_goals (id, title, topic, knowledge_source_ids, status) VALUES (?, ?, ?, ?, ?)",
            (goal_id, "Goal", "Topic", "[]", "active"),
        )
        await db.execute(
            "INSERT INTO cumulative_tests (id, goal_id, questions, created_at) VALUES (?, ?, ?, datetime('now'))",
            (test_id, goal_id, json.dumps(questions_data)),
        )
        await db.commit()

    mock_settings = MagicMock()
    mock_settings.sqlite_path = db_path
    monkeypatch.setattr(router_mod, "settings", mock_settings)

    # Answer 7/10 correctly (first 7 get index 0, last 3 get wrong index)
    answers = {qid: 0 for qid in question_ids[:7]}
    answers.update({qid: 3 for qid in question_ids[7:]})

    body = TestSubmitRequest(answers=answers)
    result = await router_mod.submit_final_test(goal_id, body)

    assert abs(result["score"] - 0.70) < 0.001
    assert result["goal_complete"] is True

    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT status FROM study_goals WHERE id=?", (goal_id,)) as cur:
            row = await cur.fetchone()
    assert row[0] == "complete"


# ── TST-06: weak_session_numbers ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_submit_returns_weak_session_numbers(tmp_db, monkeypatch):
    """TST-06: session with < 50% correct appears in weak_session_numbers."""
    import app.routers.test as router_mod
    from app.routers.test import TestSubmitRequest

    db_path, goal_id, session1_id, session2_id = tmp_db

    # 2 questions for session 1, 2 questions for session 2
    q_s1a = str(uuid.uuid4())
    q_s1b = str(uuid.uuid4())
    q_s2a = str(uuid.uuid4())
    q_s2b = str(uuid.uuid4())
    test_id = str(uuid.uuid4())

    questions_data = [
        {"id": q_s1a, "session_number": 1, "question": "S1Q1?", "options": ["A","B","C","D"], "correct_index": 0, "explanation": "A"},
        {"id": q_s1b, "session_number": 1, "question": "S1Q2?", "options": ["A","B","C","D"], "correct_index": 0, "explanation": "A"},
        {"id": q_s2a, "session_number": 2, "question": "S2Q1?", "options": ["A","B","C","D"], "correct_index": 1, "explanation": "B"},
        {"id": q_s2b, "session_number": 2, "question": "S2Q2?", "options": ["A","B","C","D"], "correct_index": 1, "explanation": "B"},
    ]

    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO cumulative_tests (id, goal_id, questions, created_at) VALUES (?, ?, ?, datetime('now'))",
            (test_id, goal_id, json.dumps(questions_data)),
        )
        await db.commit()

    mock_settings = MagicMock()
    mock_settings.sqlite_path = db_path
    monkeypatch.setattr(router_mod, "settings", mock_settings)

    # Session 1: 0/2 correct (both wrong) → weak
    # Session 2: 2/2 correct → strong
    body = TestSubmitRequest(answers={
        q_s1a: 3, q_s1b: 3,   # wrong for session 1
        q_s2a: 1, q_s2b: 1,   # correct for session 2
    })
    result = await router_mod.submit_final_test(goal_id, body)

    assert 1 in result["weak_session_numbers"]
    assert 2 not in result["weak_session_numbers"]


@pytest.mark.asyncio
async def test_submit_mixed_weak_sessions(tmp_db, monkeypatch):
    """TST-06: session 1 weak, session 2 strong — weak_session_numbers == [1]."""
    import app.routers.test as router_mod
    from app.routers.test import TestSubmitRequest

    db_path, goal_id, session1_id, session2_id = tmp_db

    q_s1a = str(uuid.uuid4())
    q_s2a = str(uuid.uuid4())
    test_id = str(uuid.uuid4())

    questions_data = [
        {"id": q_s1a, "session_number": 1, "question": "S1Q1?", "options": ["A","B","C","D"], "correct_index": 0, "explanation": "A"},
        {"id": q_s2a, "session_number": 2, "question": "S2Q1?", "options": ["A","B","C","D"], "correct_index": 1, "explanation": "B"},
    ]

    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO cumulative_tests (id, goal_id, questions, created_at) VALUES (?, ?, ?, datetime('now'))",
            (test_id, goal_id, json.dumps(questions_data)),
        )
        await db.commit()

    mock_settings = MagicMock()
    mock_settings.sqlite_path = db_path
    monkeypatch.setattr(router_mod, "settings", mock_settings)

    # Session 1: wrong, Session 2: correct
    body = TestSubmitRequest(answers={q_s1a: 3, q_s2a: 1})
    result = await router_mod.submit_final_test(goal_id, body)

    assert result["weak_session_numbers"] == [1]


# ── ORC-01: ScholarState V2 annotations ─────────────────────────────────────

def test_scholar_state_has_v2_annotations():
    """ORC-01: ScholarState.__annotations__ contains all V2 keys."""
    from app.agents.orchestrator import ScholarState

    annotations = ScholarState.__annotations__
    required_v2_keys = [
        "sessions_complete",
        "weak_session_ids",
        "followup_sessions_added",
        "final_test_id",
        "goal_complete",
    ]
    for key in required_v2_keys:
        assert key in annotations, f"Missing V2 annotation: {key}"


# ── ORC-02: update_goal_progress() returns correct shape ─────────────────────

@pytest.mark.asyncio
async def test_update_goal_progress_returns_correct_shape(tmp_db, monkeypatch):
    """ORC-02: goal with all sessions complete returns sessions_complete=True."""
    import app.agents.orchestrator as orc_mod

    db_path, goal_id, session1_id, session2_id = tmp_db

    mock_settings = MagicMock()
    mock_settings.sqlite_path = db_path
    monkeypatch.setattr(orc_mod, "settings", mock_settings)

    result = await orc_mod.update_goal_progress(goal_id)

    assert "sessions_complete" in result
    assert "goal_complete" in result
    assert "weak_session_ids" in result
    assert result["sessions_complete"] is True
    assert result["goal_complete"] is False  # goal status is 'active'
    assert isinstance(result["weak_session_ids"], list)


@pytest.mark.asyncio
async def test_update_goal_progress_identifies_weak_sessions(tmp_db, monkeypatch):
    """ORC-02: session with quiz_score=0.50 (< 0.65) appears in weak_session_ids."""
    import app.agents.orchestrator as orc_mod

    db_path, goal_id, session1_id, session2_id = tmp_db

    # Set session1 quiz_score to 0.50 (below PASS_THRESHOLD of 0.65)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE study_sessions SET quiz_score=0.50 WHERE id=?", (session1_id,)
        )
        await db.commit()

    mock_settings = MagicMock()
    mock_settings.sqlite_path = db_path
    monkeypatch.setattr(orc_mod, "settings", mock_settings)

    result = await orc_mod.update_goal_progress(goal_id)

    assert session1_id in result["weak_session_ids"]
    assert session2_id not in result["weak_session_ids"]


@pytest.mark.asyncio
async def test_update_goal_progress_nonexistent_goal(tmp_db, monkeypatch):
    """ORC-02: non-existent goal_id returns empty dict {}."""
    import app.agents.orchestrator as orc_mod

    db_path, goal_id, session1_id, session2_id = tmp_db

    mock_settings = MagicMock()
    mock_settings.sqlite_path = db_path
    monkeypatch.setattr(orc_mod, "settings", mock_settings)

    result = await orc_mod.update_goal_progress("nonexistent-goal-id")

    assert result == {}
