"""Tests for evaluate_quiz (pure Python, no LLM) and generate_quiz (mocked LLM)."""
import pytest
from unittest.mock import MagicMock, patch
from app.agents.quiz_agent import (
    QuizQuestion,
    evaluate_quiz,
    generate_quiz,
)


def _make_questions(n: int = 3) -> list[QuizQuestion]:
    return [
        QuizQuestion(
            id=f"q{i}",
            question=f"Question {i}?",
            options=["A", "B", "C", "D"],
            correct_index=0,
            explanation=f"A is correct for {i}.",
        )
        for i in range(1, n + 1)
    ]


class TestEvaluateQuiz:
    def test_all_correct_score_is_one(self):
        questions = _make_questions(5)
        answers = {q.id: 0 for q in questions}  # correct_index=0 for all
        result = evaluate_quiz(questions, answers)
        assert result.score == 1.0
        assert result.correct_count == 5
        assert result.total_questions == 5

    def test_all_wrong_score_is_zero(self):
        questions = _make_questions(5)
        answers = {q.id: 3 for q in questions}  # wrong — correct_index=0
        result = evaluate_quiz(questions, answers)
        assert result.score == 0.0
        assert result.correct_count == 0

    def test_partial_score(self):
        questions = _make_questions(4)
        answers = {
            "q1": 0,  # correct
            "q2": 0,  # correct
            "q3": 2,  # wrong
            "q4": 1,  # wrong
        }
        result = evaluate_quiz(questions, answers)
        assert result.correct_count == 2
        assert result.score == pytest.approx(0.5)

    def test_missing_answer_counts_as_wrong(self):
        questions = _make_questions(2)
        result = evaluate_quiz(questions, {})  # no answers submitted
        assert result.correct_count == 0
        assert result.score == 0.0

    def test_per_question_count_matches(self):
        questions = _make_questions(5)
        answers = {q.id: 0 for q in questions}
        result = evaluate_quiz(questions, answers)
        assert len(result.per_question) == 5

    def test_per_question_reveals_correct_index(self):
        questions = _make_questions(1)
        result = evaluate_quiz(questions, {"q1": 2})  # wrong answer
        pq = result.per_question[0]
        assert pq.correct is False
        assert pq.correct_index == 0  # revealed after submission
        assert pq.explanation == "A is correct for 1."

    def test_empty_questions_returns_zero_score(self):
        result = evaluate_quiz([], {})
        assert result.score == 0.0
        assert result.total_questions == 0


@pytest.mark.asyncio
async def test_generate_quiz_calls_chain_and_returns_questions():
    """generate_quiz returns list[QuizQuestion] from mocked chain."""
    mock_questions = _make_questions(5)
    mock_output = MagicMock()
    mock_output.questions = mock_questions

    with patch(
        "app.agents.quiz_agent._quiz_chain",
        new=MagicMock(invoke=MagicMock(return_value=mock_output)),
    ):
        result = await generate_quiz(
            session_id="sess-1",
            notes_markdown="# Biology\n\nPhotosynthesis converts light to energy.",
            topic="Biology",
            level="beginner",
        )

    assert len(result) == 5
    assert all(isinstance(q, QuizQuestion) for q in result)
