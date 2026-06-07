import asyncio
import uuid
from app.core.logging import get_logger

from pydantic import BaseModel

from app.llm_factory import get_llm
from app.retrieval.hybrid_retriever import retrieve

logger = get_logger(__name__)

MAX_TEST_QUESTIONS = 15
QUESTIONS_PER_SESSION = 2  # target; LLM may return 1 or 2


class TestQuestion(BaseModel):
    id: str
    session_number: int      # CRITICAL: enables weak_session_numbers calculation
    question: str
    options: list[str]       # exactly 4 items
    correct_index: int       # never sent to frontend; stored in SQLite only
    explanation: str


class TestOutput(BaseModel):
    questions: list[TestQuestion]


_test_chain = get_llm(temperature=0.3).with_structured_output(TestOutput)


async def generate_test(
    sessions: list[dict],       # list of {session_number, topic} dicts
    source_ids: list[str],
) -> list[TestQuestion]:
    """Generate 1-2 MCQ questions per session, capped at MAX_TEST_QUESTIONS total.

    Each session gets its own LLM call with retrieved context — avoids
    single large prompt that may exceed context limits for many sessions.
    """
    all_questions: list[TestQuestion] = []

    for session in sessions:
        if len(all_questions) >= MAX_TEST_QUESTIONS:
            break

        session_number = session["session_number"]
        topic = session["topic"]

        # Retrieve top-3 context chunks for this session's topic
        try:
            retrieval_result = await retrieve(
                query=topic,
                source_ids=source_ids,
                top_k=3,
            )
            context_str = "\n\n".join(c.content for c in retrieval_result.chunks)
        except Exception:
            logger.warning(
                "Retrieval failed for session %d topic '%s' — skipping",
                session_number,
                topic,
            )
            continue

        # Build prompt requesting 1-2 questions for this session
        remaining = MAX_TEST_QUESTIONS - len(all_questions)
        questions_to_generate = min(QUESTIONS_PER_SESSION, remaining)

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a study test generator. Generate exactly "
                    f"{questions_to_generate} multiple-choice question(s) "
                    "grounded ONLY in the provided context. "
                    "Each question must have exactly 4 options (options list length = 4). "
                    f"Set session_number={session_number} on every question you generate."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Session topic: {topic}\n\n"
                    f"Context:\n{context_str[:3000]}"
                ),
            },
        ]

        result = await asyncio.to_thread(_test_chain.invoke, messages)

        # Always assign a fresh unique ID — the LLM tends to reuse "q1"/"q2" across
        # sessions, which would collide when questions are aggregated into one test
        # (breaking React keys and answer submission, which is keyed by question id).
        for q in result.questions:
            q.id = str(uuid.uuid4())
            q.session_number = session_number  # enforce tagging regardless of LLM output

        all_questions.extend(result.questions)

    return all_questions[:MAX_TEST_QUESTIONS]
