"""
Tests for Phase 11: Final Test Agent + Orchestrator V2.

All tests use monkeypatching for LLM calls. Database seeding uses the ORM
against the test Postgres instance (same DB the app uses).

Coverage:
    TST-01 / TST-02  — generate_test() tags session_number; caps at MAX_TEST_QUESTIONS
    TST-03           — SKIPPED (init_db() removed; schema managed by ORM + Postgres)
    TST-04           — generate_final_test() returns 400 for incomplete/no sessions
    TST-05           — submit_final_test() marks goal complete when score >= 0.70
    TST-06           — submit_final_test() returns weak_session_numbers
    ORC-01           — ScholarState TypedDict has V2 annotations
    ORC-02           — update_goal_progress() returns correct shape
"""
import asyncio
import json
import uuid

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models.db_models import StudyGoal, StudySession, CumulativeTest


# ── ORM seed helpers ─────────────────────────────────────────────────────────

def _make_session_factory():
    url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(url, poolclass=NullPool, echo=False)
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession), engine


async def _seed_goal_and_two_complete_sessions():
    """Seed: one active goal + two complete sessions. Returns (goal_id, s1_id, s2_id)."""
    goal_id = str(uuid.uuid4())
    s1_id = str(uuid.uuid4())
    s2_id = str(uuid.uuid4())

    factory, engine = _make_session_factory()
    async with factory() as session:
        session.add(StudyGoal(
            id=goal_id,
            title="Biology Goal",
            topic="Cell Biology",
            knowledge_source_ids="[]",
            status="active",
            created_at="2026-01-01T00:00:00",
        ))
        session.add(StudySession(
            id=s1_id,
            goal_id=goal_id,
            session_number=1,
            title="Session 1: Cells",
            topic="Cells",
            estimated_minutes=45,
            status="complete",
            created_at="2026-01-01T00:00:00",
        ))
        session.add(StudySession(
            id=s2_id,
            goal_id=goal_id,
            session_number=2,
            title="Session 2: DNA",
            topic="DNA",
            estimated_minutes=45,
            status="complete",
            created_at="2026-01-01T00:00:00",
        ))
        await session.commit()
    await engine.dispose()
    return goal_id, s1_id, s2_id


async def _seed_cumulative_test(goal_id: str, questions_json: str) -> str:
    """Seed a cumulative_tests row. Returns test_id."""
    test_id = str(uuid.uuid4())
    factory, engine = _make_session_factory()
    async with factory() as session:
        session.add(CumulativeTest(
            id=test_id,
            goal_id=goal_id,
            questions=questions_json,
            created_at="2026-01-01T00:00:00",
        ))
        await session.commit()
    await engine.dispose()
    return test_id


async def _get_goal_status(goal_id: str) -> str | None:
    factory, engine = _make_session_factory()
    async with factory() as session:
        obj = await session.get(StudyGoal, goal_id)
        status = obj.status if obj else None
    await engine.dispose()
    return status


async def _set_session_status(session_id: str, status: str):
    factory, engine = _make_session_factory()
    async with factory() as session:
        obj = await session.get(StudySession, session_id)
        if obj:
            obj.status = status
            await session.commit()
    await engine.dispose()


async def _set_session_quiz_score(session_id: str, score: float):
    factory, engine = _make_session_factory()
    async with factory() as session:
        obj = await session.get(StudySession, session_id)
        if obj:
            obj.quiz_score = score
            await session.commit()
    await engine.dispose()


# ── Fixtures ─────────────────────────────────────────────────────────────────

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
    """TST-01/TST-02: generate_test() enforces session_number post-LLM on every question."""
    import app.agents.test_agent as ta_mod
    from app.agents.test_agent import TestOutput, TestQuestion, generate_test

    def make_output(session_number_from_llm: int) -> TestOutput:
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

    assert len(questions) == 4
    assert questions[0].session_number == 1
    assert questions[1].session_number == 1
    assert questions[2].session_number == 2
    assert questions[3].session_number == 2


@pytest.mark.asyncio
async def test_generate_test_caps_at_15_questions(monkeypatch, mock_retrieve):
    """TST-01: with 8 sessions returning 2 questions each, result is capped at 15."""
    import app.agents.test_agent as ta_mod
    from app.agents.test_agent import TestOutput, TestQuestion, generate_test

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

@pytest.mark.skip(
    reason=(
        "TST-03 verified init_db() creates cumulative_tests in SQLite. "
        "init_db() was removed in the SQLite→Postgres migration. The schema is now "
        "managed by SQLAlchemy ORM (CumulativeTest model) + init_orm_models(). "
        "The model declaration IS the spec; table presence is guaranteed by create_all "
        "at app startup."
    )
)
def test_init_db_creates_cumulative_tests_table():
    pass


@pytest.mark.skip(reason="init_db() removed — see test_init_db_creates_cumulative_tests_table")
def test_init_db_idempotent():
    pass


# ── TST-04: generate_final_test returns 400 for bad goal state ────────────────

@pytest.mark.asyncio
async def test_generate_endpoint_400_when_sessions_incomplete(
    monkeypatched_chain, mock_retrieve
):
    """TST-04: goal with a pending session returns 400."""
    import app.routers.test as router_mod
    from fastapi import HTTPException

    goal_id, s1_id, s2_id = await _seed_goal_and_two_complete_sessions()
    # Make s2 pending
    await _set_session_status(s2_id, "pending")

    with pytest.raises(HTTPException) as exc_info:
        await router_mod.generate_final_test(goal_id)

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_generate_endpoint_400_when_no_sessions():
    """TST-04: goal with no sessions returns 400."""
    import app.routers.test as router_mod
    from fastapi import HTTPException

    goal_id = str(uuid.uuid4())
    factory, engine = _make_session_factory()
    async with factory() as session:
        session.add(StudyGoal(
            id=goal_id,
            title="Empty Goal",
            topic="Nothing",
            knowledge_source_ids="[]",
            status="active",
            created_at="2026-01-01T00:00:00",
        ))
        await session.commit()
    await engine.dispose()

    with pytest.raises(HTTPException) as exc_info:
        await router_mod.generate_final_test(goal_id)

    assert exc_info.value.status_code == 400


# ── TST-05: submit_final_test marks goal complete at score >= 0.70 ─────────────

def _build_questions_json(q1_id: str, q2_id: str) -> str:
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


@pytest.mark.asyncio
async def test_submit_marks_goal_complete_on_passing_score():
    """TST-05: score=1.0 (all correct) marks goal.status='complete'."""
    import app.routers.test as router_mod
    from app.routers.test import TestSubmitRequest

    goal_id, s1_id, s2_id = await _seed_goal_and_two_complete_sessions()
    q1_id = str(uuid.uuid4())
    q2_id = str(uuid.uuid4())
    await _seed_cumulative_test(goal_id, _build_questions_json(q1_id, q2_id))

    body = TestSubmitRequest(answers={q1_id: 0, q2_id: 1})
    result = await router_mod.submit_final_test(goal_id, body)

    assert result["score"] == 1.0
    assert result["goal_complete"] is True

    status = await _get_goal_status(goal_id)
    assert status == "complete"


@pytest.mark.asyncio
async def test_submit_does_not_mark_complete_on_fail():
    """TST-05: score=0.0 (all wrong) — goal.status stays 'active'."""
    import app.routers.test as router_mod
    from app.routers.test import TestSubmitRequest

    goal_id, s1_id, s2_id = await _seed_goal_and_two_complete_sessions()
    q1_id = str(uuid.uuid4())
    q2_id = str(uuid.uuid4())
    await _seed_cumulative_test(goal_id, _build_questions_json(q1_id, q2_id))

    body = TestSubmitRequest(answers={q1_id: 3, q2_id: 3})
    result = await router_mod.submit_final_test(goal_id, body)

    assert result["score"] == 0.0
    assert result["goal_complete"] is False

    status = await _get_goal_status(goal_id)
    assert status == "active"


@pytest.mark.asyncio
async def test_submit_exactly_70_percent_marks_complete():
    """TST-05: exactly 70% correct (7/10) marks goal complete."""
    import app.routers.test as router_mod
    from app.routers.test import TestSubmitRequest

    goal_id = str(uuid.uuid4())
    factory, engine = _make_session_factory()
    async with factory() as session:
        session.add(StudyGoal(
            id=goal_id,
            title="Goal",
            topic="Topic",
            knowledge_source_ids="[]",
            status="active",
            created_at="2026-01-01T00:00:00",
        ))
        await session.commit()
    await engine.dispose()

    question_ids = [str(uuid.uuid4()) for _ in range(10)]
    questions_data = [
        {
            "id": qid,
            "session_number": 1,
            "question": f"Q{i}?",
            "options": ["A", "B", "C", "D"],
            "correct_index": 0,
            "explanation": "A is correct.",
        }
        for i, qid in enumerate(question_ids)
    ]
    await _seed_cumulative_test(goal_id, json.dumps(questions_data))

    answers = {qid: 0 for qid in question_ids[:7]}
    answers.update({qid: 3 for qid in question_ids[7:]})
    body = TestSubmitRequest(answers=answers)
    result = await router_mod.submit_final_test(goal_id, body)

    assert abs(result["score"] - 0.70) < 0.001
    assert result["goal_complete"] is True

    status = await _get_goal_status(goal_id)
    assert status == "complete"


# ── TST-06: weak_session_numbers ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_submit_returns_weak_session_numbers():
    """TST-06: session with < 50% correct appears in weak_session_numbers."""
    import app.routers.test as router_mod
    from app.routers.test import TestSubmitRequest

    goal_id, s1_id, s2_id = await _seed_goal_and_two_complete_sessions()

    q_s1a = str(uuid.uuid4())
    q_s1b = str(uuid.uuid4())
    q_s2a = str(uuid.uuid4())
    q_s2b = str(uuid.uuid4())

    questions_data = [
        {"id": q_s1a, "session_number": 1, "question": "S1Q1?", "options": ["A","B","C","D"], "correct_index": 0, "explanation": "A"},
        {"id": q_s1b, "session_number": 1, "question": "S1Q2?", "options": ["A","B","C","D"], "correct_index": 0, "explanation": "A"},
        {"id": q_s2a, "session_number": 2, "question": "S2Q1?", "options": ["A","B","C","D"], "correct_index": 1, "explanation": "B"},
        {"id": q_s2b, "session_number": 2, "question": "S2Q2?", "options": ["A","B","C","D"], "correct_index": 1, "explanation": "B"},
    ]
    await _seed_cumulative_test(goal_id, json.dumps(questions_data))

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
async def test_submit_mixed_weak_sessions():
    """TST-06: session 1 weak, session 2 strong — weak_session_numbers == [1]."""
    import app.routers.test as router_mod
    from app.routers.test import TestSubmitRequest

    goal_id, s1_id, s2_id = await _seed_goal_and_two_complete_sessions()

    q_s1a = str(uuid.uuid4())
    q_s2a = str(uuid.uuid4())

    questions_data = [
        {"id": q_s1a, "session_number": 1, "question": "S1Q1?", "options": ["A","B","C","D"], "correct_index": 0, "explanation": "A"},
        {"id": q_s2a, "session_number": 2, "question": "S2Q1?", "options": ["A","B","C","D"], "correct_index": 1, "explanation": "B"},
    ]
    await _seed_cumulative_test(goal_id, json.dumps(questions_data))

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
async def test_update_goal_progress_returns_correct_shape():
    """ORC-02: goal with all sessions complete returns sessions_complete=True."""
    import app.agents.orchestrator as orc_mod

    goal_id, s1_id, s2_id = await _seed_goal_and_two_complete_sessions()

    result = await orc_mod.update_goal_progress(goal_id)

    assert "sessions_complete" in result
    assert "goal_complete" in result
    assert "weak_session_ids" in result
    assert result["sessions_complete"] is True
    assert result["goal_complete"] is False  # goal status is 'active'
    assert isinstance(result["weak_session_ids"], list)


@pytest.mark.asyncio
async def test_update_goal_progress_identifies_weak_sessions():
    """ORC-02: session with quiz_score=0.50 (< 0.65) appears in weak_session_ids."""
    import app.agents.orchestrator as orc_mod

    goal_id, s1_id, s2_id = await _seed_goal_and_two_complete_sessions()
    await _set_session_quiz_score(s1_id, 0.50)

    result = await orc_mod.update_goal_progress(goal_id)

    assert s1_id in result["weak_session_ids"]
    assert s2_id not in result["weak_session_ids"]


@pytest.mark.asyncio
async def test_update_goal_progress_nonexistent_goal():
    """ORC-02: non-existent goal_id returns empty dict {}."""
    import app.agents.orchestrator as orc_mod

    result = await orc_mod.update_goal_progress("nonexistent-goal-id")

    assert result == {}
