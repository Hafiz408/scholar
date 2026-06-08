import json
from app.core.logging import get_logger
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update, func

from app.config import settings
from app.core.database import get_session
from app.models.db_models import StudyGoal, StudySession, CumulativeTest, to_dict
from app.agents.test_agent import TestQuestion, generate_test
from app.agents.quiz_agent import evaluate_quiz, QuizQuestion

logger = get_logger(__name__)

router = APIRouter(prefix="/goals", tags=["test"])

FINAL_TEST_PASS_THRESHOLD = 0.70
WEAK_SESSION_THRESHOLD = 0.50


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TestQuestionPublic(BaseModel):
    """Test question without correct_index — safe to send to frontend."""
    id: str
    session_number: int
    question: str
    options: list[str]


class TestSubmitRequest(BaseModel):
    answers: dict[str, int]   # question_id -> selected_index (0-3)


def _compute_weak_sessions(
    questions: list[TestQuestion],
    per_question_results,
) -> list[int]:
    """Return sorted list of session_numbers where correct/total < WEAK_SESSION_THRESHOLD."""
    session_stats: dict[int, dict] = defaultdict(lambda: {"correct": 0, "total": 0})
    q_to_session = {q.id: q.session_number for q in questions}
    for pqr in per_question_results:
        snum = q_to_session.get(pqr.question_id)
        if snum is None:
            continue
        session_stats[snum]["total"] += 1
        if pqr.correct:
            session_stats[snum]["correct"] += 1
    weak = []
    for snum, stats in session_stats.items():
        if stats["total"] > 0 and stats["correct"] / stats["total"] < WEAK_SESSION_THRESHOLD:
            weak.append(snum)
    return sorted(weak)


@router.post("/{goal_id}/test/generate")
async def generate_final_test(goal_id: str) -> list[TestQuestionPublic]:
    """Generate cumulative MCQ test. Returns 400 if not all sessions are complete."""
    async with get_session() as session:
        # Guard 1: goal must exist
        goal_obj = (
            await session.execute(
                select(StudyGoal).where(StudyGoal.id == goal_id)
            )
        ).scalar_one_or_none()

        if goal_obj is None:
            raise HTTPException(status_code=404, detail="Goal not found")

        # Guard 2: goal must have at least one session
        total_count = (
            await session.execute(
                select(func.count()).select_from(StudySession).where(StudySession.goal_id == goal_id)
            )
        ).scalar_one()

        if total_count == 0:
            raise HTTPException(status_code=400, detail="Goal has no sessions")

        # Guard 3: ALL sessions must be complete (TST-04)
        incomplete_count = (
            await session.execute(
                select(func.count())
                .select_from(StudySession)
                .where(StudySession.goal_id == goal_id, StudySession.status != "complete")
            )
        ).scalar_one()

        if incomplete_count > 0:
            raise HTTPException(
                status_code=400,
                detail="Not all sessions are complete — complete all sessions before taking the final test",
            )

        # Fetch sessions for question generation
        session_rows = (
            await session.execute(
                select(StudySession)
                .where(StudySession.goal_id == goal_id)
                .order_by(StudySession.session_number)
            )
        ).scalars().all()

    sessions = [{"session_number": r.session_number, "topic": r.topic} for r in session_rows]
    source_ids = json.loads(goal_obj.knowledge_source_ids or "[]")

    questions = await generate_test(sessions=sessions, source_ids=source_ids)

    if not questions:
        raise HTTPException(status_code=500, detail="Test generation produced no questions")

    # Persist full questions (with correct_index and session_number) to cumulative_tests
    test_id = str(uuid.uuid4())
    questions_json = json.dumps([q.model_dump() for q in questions])
    async with get_session() as session:
        session.add(
            CumulativeTest(
                id=test_id,
                goal_id=goal_id,
                questions=questions_json,
                created_at=_now(),
            )
        )
        await session.commit()

    # Return public-safe version WITHOUT correct_index
    return [
        TestQuestionPublic(
            id=q.id,
            session_number=q.session_number,
            question=q.question,
            options=q.options,
        )
        for q in questions
    ]


@router.post("/{goal_id}/test/submit")
async def submit_final_test(goal_id: str, body: TestSubmitRequest) -> dict:
    """Score answers against the most recent test. Marks goal complete if score >= 70%."""
    async with get_session() as session:
        # Load most recent test for this goal
        test_obj = (
            await session.execute(
                select(CumulativeTest)
                .where(CumulativeTest.goal_id == goal_id)
                .order_by(CumulativeTest.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    if test_obj is None:
        raise HTTPException(status_code=422, detail="No test found for this goal — generate a test first")

    test_id = test_obj.id
    raw = json.loads(test_obj.questions)
    questions = [TestQuestion(**q) for q in raw]

    # Cast TestQuestion to QuizQuestion for evaluate_quiz() reuse
    # Both have id, correct_index, explanation — compatible field set
    quiz_qs = [
        QuizQuestion(
            id=q.id,
            question=q.question,
            options=q.options,
            correct_index=q.correct_index,
            explanation=q.explanation,
        )
        for q in questions
    ]

    result = evaluate_quiz(quiz_qs, body.answers)

    weak_session_numbers = _compute_weak_sessions(questions, result.per_question)

    # Persist score and weak_session_numbers to cumulative_tests
    async with get_session() as session:
        await session.execute(
            update(CumulativeTest)
            .where(CumulativeTest.id == test_id)
            .values(score=result.score, weak_session_numbers=json.dumps(weak_session_numbers))
        )
        # Mark goal complete if score >= threshold (TST-05)
        if result.score >= FINAL_TEST_PASS_THRESHOLD:
            await session.execute(
                update(StudyGoal)
                .where(StudyGoal.id == goal_id)
                .values(status="complete")
            )
        await session.commit()

    return {
        "score": result.score,
        "total_questions": result.total_questions,
        "correct_count": result.correct_count,
        "goal_complete": result.score >= FINAL_TEST_PASS_THRESHOLD,
        "weak_session_numbers": weak_session_numbers,
        "per_question": [pq.model_dump() for pq in result.per_question],
    }
