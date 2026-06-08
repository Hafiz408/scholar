import asyncio
import uuid
from pydantic import BaseModel
from app.core.llm_factory import get_llm
from app.agents.prompts import QUIZ_SYSTEM_PROMPT


class QuizQuestion(BaseModel):
    id: str
    question: str
    options: list[str]   # exactly 4 items
    correct_index: int   # 0-3, NEVER sent to frontend during generation
    explanation: str


class QuizOutput(BaseModel):
    questions: list[QuizQuestion]


class PerQuestionResult(BaseModel):
    question_id: str
    correct: bool
    explanation: str
    correct_index: int   # revealed only after submission


class QuizResult(BaseModel):
    score: float          # 0.0-1.0
    total_questions: int
    correct_count: int
    per_question: list[PerQuestionResult]


def _make_quiz_chain():
    return get_llm(temperature=0.3).with_structured_output(QuizOutput)


_quiz_chain = _make_quiz_chain()


async def generate_quiz(
    session_id: str,
    notes_markdown: str,
    topic: str,
    level: str,
) -> list[QuizQuestion]:
    """Generate 5 MCQ questions grounded in session notes via structured output."""
    messages = [
        {"role": "system", "content": QUIZ_SYSTEM_PROMPT.format(level=level)},
        {
            "role": "user",
            "content": (
                f"Topic: {topic}\n\n"
                f"Session notes:\n{notes_markdown[:4000]}"
            ),
        },
    ]
    result = await asyncio.to_thread(_quiz_chain.invoke, messages)
    # Always assign a fresh unique id — answers are keyed by question id on submit,
    # so LLM-reused ids (e.g. "q1"/"q2") would collide and corrupt scoring.
    for q in result.questions:
        q.id = str(uuid.uuid4())
    return result.questions


def evaluate_quiz(
    questions: list[QuizQuestion],
    answers: dict[str, int],
) -> QuizResult:
    """Pure-Python evaluation — no LLM call."""
    per_question = []
    correct_count = 0
    for q in questions:
        selected = answers.get(q.id)
        is_correct = selected == q.correct_index
        if is_correct:
            correct_count += 1
        per_question.append(
            PerQuestionResult(
                question_id=q.id,
                correct=is_correct,
                explanation=q.explanation,
                correct_index=q.correct_index,
            )
        )
    total = len(questions)
    score = correct_count / total if total > 0 else 0.0
    return QuizResult(
        score=score,
        total_questions=total,
        correct_count=correct_count,
        per_question=per_question,
    )
