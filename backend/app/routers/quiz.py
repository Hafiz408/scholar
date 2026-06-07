import json
from app.core.logging import get_logger
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update

from app.config import settings
from app.core.database import get_session
from app.models.db_models import StudySession, StudyGoal, to_dict
from app.agents.quiz_agent import generate_quiz, evaluate_quiz, QuizQuestion, QuizResult

logger = get_logger(__name__)

router = APIRouter(prefix="/sessions", tags=["quiz"])


class QuizQuestionPublic(BaseModel):
    """Quiz question without correct_index — safe to send to frontend."""
    id: str
    question: str
    options: list[str]


class QuizSubmitRequest(BaseModel):
    answers: dict[str, int]   # question_id -> selected_index (0-3)


@router.post("/{session_id}/quiz/generate")
async def generate_session_quiz(session_id: str) -> list[QuizQuestionPublic]:
    """Generate 5 MCQ questions for a session. Does NOT expose correct_index."""
    # Fetch session context via join
    async with get_session() as session:
        result = (
            await session.execute(
                select(StudySession, StudyGoal)
                .join(StudyGoal, StudySession.goal_id == StudyGoal.id)
                .where(StudySession.id == session_id)
            )
        ).one_or_none()

    if result is None:
        raise HTTPException(status_code=404, detail="Session not found")

    sess_obj, goal_obj = result
    row = to_dict(sess_obj)

    notes_markdown = row["notes_markdown"]
    if not notes_markdown:
        raise HTTPException(
            status_code=422,
            detail="Session has no notes yet — start the session first to generate notes"
        )

    questions = await generate_quiz(
        session_id=session_id,
        notes_markdown=notes_markdown,
        topic=row["topic"],
        level=goal_obj.level,
    )

    # Persist full questions (with correct_index) to Postgres for scoring later
    async with get_session() as session:
        questions_json = json.dumps([q.model_dump() for q in questions])
        await session.execute(
            update(StudySession)
            .where(StudySession.id == session_id)
            .values(quiz_questions=questions_json)
        )
        await session.commit()

    # Return public-safe version WITHOUT correct_index
    return [
        QuizQuestionPublic(id=q.id, question=q.question, options=q.options)
        for q in questions
    ]


@router.post("/{session_id}/quiz/submit")
async def submit_session_quiz(session_id: str, body: QuizSubmitRequest) -> dict:
    """Submit quiz answers — returns score and per-question results. Marks session complete."""
    async with get_session() as session:
        obj = (
            await session.execute(
                select(StudySession).where(StudySession.id == session_id)
            )
        ).scalar_one_or_none()

    if obj is None:
        raise HTTPException(status_code=404, detail="Session not found")

    row = to_dict(obj)
    quiz_questions_json = row["quiz_questions"]
    if not quiz_questions_json:
        raise HTTPException(status_code=422, detail="No quiz found for this session — generate quiz first")

    # Reconstruct QuizQuestion objects (with correct_index, from Postgres)
    raw_questions = json.loads(quiz_questions_json)
    questions = [QuizQuestion(**q) for q in raw_questions]

    result = evaluate_quiz(questions, body.answers)

    # Persist score and mark session complete
    async with get_session() as session:
        await session.execute(
            update(StudySession)
            .where(StudySession.id == session_id)
            .values(quiz_score=result.score, status="complete")
        )
        await session.commit()

    # Attempt adaptive planning AFTER score is committed — ADP-04
    followup_result = {"followup_session_added": False, "followup_session": None}
    try:
        from app.agents.adaptive_planner import handle_quiz_failure
        followup_result = await handle_quiz_failure(session_id)
    except Exception as e:
        logger.error("Adaptive planner failed for session %s: %s", session_id, e)

    return {
        "score": result.score,
        "total_questions": result.total_questions,
        "correct_count": result.correct_count,
        "per_question": [pq.model_dump() for pq in result.per_question],
        **followup_result,
    }
