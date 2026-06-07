import asyncio
import json
from datetime import datetime, timezone
from app.core.logging import get_logger
import uuid

from sqlalchemy import select, update
from app.core.database import get_session
from app.models.db_models import to_dict, KnowledgeSource, StudySession, StudyGoal
from app.agents.planner import SessionPlan
from app.agents.prompts import ADAPTIVE_PLANNER_SYSTEM_PROMPT
from app.core.llm_factory import get_llm

logger = get_logger(__name__)

PASS_THRESHOLD = 0.65  # score < 0.65 triggers follow-up; score == 0.65 does NOT

_adaptive_chain = get_llm(temperature=0).with_structured_output(SessionPlan)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def generate_followup_session(
    topic: str,
    failed_session_number: int,
    level: str,
    source_titles: list[str],
) -> SessionPlan:
    """Call LLM to generate one remediation session for the failed topic."""
    messages = [
        {"role": "system", "content": ADAPTIVE_PLANNER_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Failed topic: {topic}\n"
                f"Student level: {level}\n"
                f"Knowledge sources: {', '.join(source_titles)}\n"
                f"Original session number: {failed_session_number}"
            ),
        },
    ]
    return await asyncio.to_thread(_adaptive_chain.invoke, messages)


async def insert_followup_session(
    session,
    goal_id: str,
    after_session_number: int,
    session_plan: SessionPlan,
) -> dict:
    """Atomically renumber downstream sessions and insert the follow-up session.

    Accepts an OPEN ORM AsyncSession. Caller is responsible for commit.
    Step 1: Increment session_number for all sessions strictly after the insertion point.
    Step 2: Insert the new follow-up session at after_session_number + 1.
    """
    new_session_number = after_session_number + 1

    # Renumber all sessions after the insertion point (strictly greater-than, NOT >=)
    await session.execute(
        update(StudySession)
        .where(StudySession.goal_id == goal_id)
        .where(StudySession.session_number > after_session_number)
        .values(session_number=StudySession.session_number + 1)
    )

    # Insert the new follow-up session
    new_id = str(uuid.uuid4())
    session.add(
        StudySession(
            id=new_id,
            goal_id=goal_id,
            session_number=new_session_number,
            title=session_plan.title,
            topic=session_plan.topic,
            estimated_minutes=session_plan.estimated_minutes,
            status="pending",
            created_at=_now(),
        )
    )

    return {
        "id": new_id,
        "session_number": new_session_number,
        "title": session_plan.title,
        "topic": session_plan.topic,
        "estimated_minutes": session_plan.estimated_minutes,
        "status": "pending",
    }


async def _fetch_source_titles(source_ids: list[str]) -> list[str]:
    """Fetch knowledge source titles by ID from Postgres.

    Opens its own session. Returns list of titles (skips any not found).
    """
    async with get_session() as session:
        rows = (
            await session.execute(
                select(KnowledgeSource).where(KnowledgeSource.id.in_(source_ids))
            )
        ).scalars().all()
    return [row.title for row in rows if row.title is not None]


async def handle_quiz_failure(session_id: str) -> dict:
    """Orchestrate: fetch session context, generate follow-up, insert into plan.

    Always fetches fresh data from DB using the session UUID (never a cached number).

    Returns:
        {
            "followup_session_added": bool,
            "followup_session": dict | None
        }
    """
    # Fetch session + goal context using UUID via a JOIN
    async with get_session() as session:
        result = await session.execute(
            select(
                StudySession.quiz_score,
                StudySession.session_number,
                StudySession.topic,
                StudySession.goal_id,
                StudyGoal.level,
                StudyGoal.knowledge_source_ids,
            )
            .join(StudyGoal, StudySession.goal_id == StudyGoal.id)
            .where(StudySession.id == session_id)
        )
        row = result.mappings().one_or_none()

    # No session found or quiz not yet scored
    if row is None or row["quiz_score"] is None:
        return {"followup_session_added": False, "followup_session": None}

    # Score at or above threshold — student passed
    if row["quiz_score"] >= PASS_THRESHOLD:
        return {"followup_session_added": False, "followup_session": None}

    # Fetch knowledge source titles for the LLM prompt
    source_ids = json.loads(row["knowledge_source_ids"] or "[]")
    source_titles = await _fetch_source_titles(source_ids)

    # Generate follow-up session via LLM
    session_plan = await generate_followup_session(
        topic=row["topic"],
        failed_session_number=row["session_number"],
        level=row["level"],
        source_titles=source_titles,
    )

    # Insert follow-up session atomically (UPDATE + INSERT in one commit)
    async with get_session() as session:
        followup = await insert_followup_session(
            session, row["goal_id"], row["session_number"], session_plan
        )
        await session.commit()

    return {"followup_session_added": True, "followup_session": followup}
