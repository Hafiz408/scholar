import asyncio
from math import ceil
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from app.config import settings
from app.agents.prompts import PLANNER_SYSTEM_PROMPT


class SessionPlan(BaseModel):
    session_number: int
    title: str
    topic: str
    estimated_minutes: int
    focus_chapters: list[str]


class StudyPlanOutput(BaseModel):
    sessions: list[SessionPlan]
    rationale: str


_llm = ChatOpenAI(model=settings.llm_model, temperature=0)
_planner_chain = _llm.with_structured_output(StudyPlanOutput)


async def generate_plan(
    goal_title: str,
    topic: str,
    level: str,
    deadline_days: int,
    sessions_per_week: int,
    source_titles: list[str],
) -> StudyPlanOutput:
    """Generate a sequenced study plan using structured output via asyncio.to_thread."""
    session_count = ceil(deadline_days / 7 * sessions_per_week)
    messages = [
        {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Goal: {goal_title}\n"
                f"Topic: {topic}\n"
                f"Level: {level}\n"
                f"Total sessions required: {session_count}\n"
                f"Knowledge sources: {', '.join(source_titles)}"
            ),
        },
    ]
    return await asyncio.to_thread(_planner_chain.invoke, messages)
