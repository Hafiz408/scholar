import asyncio
import uuid
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from app.config import settings
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


_quiz_llm = ChatOpenAI(model=settings.llm_model, temperature=0.3)
_quiz_chain = _quiz_llm.with_structured_output(QuizOutput)


async def generate_quiz(
    session_id: str,
    notes_markdown: str,
    topic: str,
    level: str,
) -> list[QuizQuestion]:
    """Generate 5 MCQ questions from session notes via structured output."""
    messages = [
        {"role": "system", "content": QUIZ_SYSTEM_PROMPT.format(level=level)},
        {
            "role": "user",
            "content": (
                f"Topic: {topic}\n\n"
                f"Session Notes:\n{notes_markdown}"
            ),
        },
    ]
    result: QuizOutput = await asyncio.to_thread(_quiz_chain.invoke, messages)

    # Assign stable IDs if not already set by LLM
    questions = []
    for q in result.questions:
        if not q.id or q.id.strip() == "":
            q = q.model_copy(update={"id": str(uuid.uuid4())})
        questions.append(q)

    return questions


def evaluate_quiz(
    questions: list[QuizQuestion],
    answers: dict[str, int],
) -> QuizResult:
    """Pure Python scoring — no LLM call. answers maps question_id -> selected_index (0-3)."""
    correct_count = sum(
        1 for q in questions
        if answers.get(q.id) == q.correct_index
    )
    per_question = [
        PerQuestionResult(
            question_id=q.id,
            correct=answers.get(q.id) == q.correct_index,
            explanation=q.explanation,
            correct_index=q.correct_index,
        )
        for q in questions
    ]
    return QuizResult(
        score=correct_count / len(questions) if questions else 0.0,
        total_questions=len(questions),
        correct_count=correct_count,
        per_question=per_question,
    )
