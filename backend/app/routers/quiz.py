import aiosqlite
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.config import settings
from app.agents.quiz_agent import generate_quiz, evaluate_quiz, QuizQuestion, QuizResult

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
    # Fetch session context
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT ss.id, ss.topic, ss.notes_markdown, ss.status,
                      sg.level
               FROM study_sessions ss
               JOIN study_goals sg ON ss.goal_id = sg.id
               WHERE ss.id = ?""",
            (session_id,),
        ) as cur:
            row = await cur.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")

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
        level=row["level"],
    )

    # Persist full questions (with correct_index) to SQLite for scoring later
    async with aiosqlite.connect(settings.sqlite_path) as db:
        questions_json = json.dumps([q.model_dump() for q in questions])
        await db.execute(
            "UPDATE study_sessions SET quiz_questions=? WHERE id=?",
            (questions_json, session_id),
        )
        await db.commit()

    # Return public-safe version WITHOUT correct_index
    return [
        QuizQuestionPublic(id=q.id, question=q.question, options=q.options)
        for q in questions
    ]


@router.post("/{session_id}/quiz/submit")
async def submit_session_quiz(session_id: str, body: QuizSubmitRequest) -> QuizResult:
    """Submit quiz answers — returns score and per-question results. Marks session complete."""
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT quiz_questions, status FROM study_sessions WHERE id = ?",
            (session_id,),
        ) as cur:
            row = await cur.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")

    quiz_questions_json = row["quiz_questions"]
    if not quiz_questions_json:
        raise HTTPException(status_code=422, detail="No quiz found for this session — generate quiz first")

    # Reconstruct QuizQuestion objects (with correct_index, from SQLite)
    raw_questions = json.loads(quiz_questions_json)
    questions = [QuizQuestion(**q) for q in raw_questions]

    result = evaluate_quiz(questions, body.answers)

    # Persist score and mark session complete
    async with aiosqlite.connect(settings.sqlite_path) as db:
        await db.execute(
            "UPDATE study_sessions SET quiz_score=?, status='complete' WHERE id=?",
            (result.score, session_id),
        )
        await db.commit()

    return result
