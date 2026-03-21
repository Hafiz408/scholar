import asyncio
import json
import logging
import uuid

import aiosqlite

from app.agents.planner import SessionPlan
from app.agents.prompts import ADAPTIVE_PLANNER_SYSTEM_PROMPT
from app.config import settings
from app.llm_factory import get_llm

logger = logging.getLogger(__name__)

PASS_THRESHOLD = 0.65  # score < 0.65 triggers follow-up; score == 0.65 does NOT

_adaptive_chain = get_llm(temperature=0).with_structured_output(SessionPlan)


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
    db: aiosqlite.Connection,
    goal_id: str,
    after_session_number: int,
    session_plan: SessionPlan,
) -> dict:
    """Atomically renumber downstream sessions and insert the follow-up session.

    Accepts an OPEN aiosqlite connection. Caller is responsible for commit.
    Step 1: Increment session_number for all sessions strictly after the insertion point.
    Step 2: Insert the new follow-up session at after_session_number + 1.
    """
    new_session_number = after_session_number + 1

    # Renumber all sessions after the insertion point (strictly greater-than, NOT >=)
    await db.execute(
        """UPDATE study_sessions
           SET session_number = session_number + 1
           WHERE goal_id = ? AND session_number > ?""",
        (goal_id, after_session_number),
    )

    # Insert the new follow-up session
    new_id = str(uuid.uuid4())
    await db.execute(
        """INSERT INTO study_sessions
           (id, goal_id, session_number, title, topic, estimated_minutes, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, 'pending', datetime('now'))""",
        (
            new_id,
            goal_id,
            new_session_number,
            session_plan.title,
            session_plan.topic,
            session_plan.estimated_minutes,
        ),
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
    """Fetch knowledge source titles by ID from SQLite.

    Opens its own connection. Returns list of titles (skips any not found).
    """
    titles = []
    async with aiosqlite.connect(settings.sqlite_path) as db:
        for source_id in source_ids:
            async with db.execute(
                "SELECT title FROM knowledge_sources WHERE id = ?",
                (source_id,),
            ) as cur:
                row = await cur.fetchone()
                if row is not None:
                    titles.append(row[0])
    return titles


async def handle_quiz_failure(session_id: str) -> dict:
    """Orchestrate: fetch session context, generate follow-up, insert into plan.

    Always fetches fresh data from DB using the session UUID (never a cached number).

    Returns:
        {
            "followup_session_added": bool,
            "followup_session": dict | None
        }
    """
    # Fetch session + goal context using UUID
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT ss.quiz_score, ss.session_number, ss.topic, ss.goal_id,
                      sg.level, sg.knowledge_source_ids
               FROM study_sessions ss
               JOIN study_goals sg ON ss.goal_id = sg.id
               WHERE ss.id = ?""",
            (session_id,),
        ) as cur:
            row = await cur.fetchone()

    # No session found or quiz not yet scored
    if row is None or row["quiz_score"] is None:
        return {"followup_session_added": False, "followup_session": None}

    # Score at or above threshold — student passed
    if row["quiz_score"] >= PASS_THRESHOLD:
        return {"followup_session_added": False, "followup_session": None}

    # Fetch knowledge source titles for the LLM prompt
    source_ids = json.loads(row["knowledge_source_ids"])
    source_titles = await _fetch_source_titles(source_ids)

    # Generate follow-up session via LLM
    session_plan = await generate_followup_session(
        topic=row["topic"],
        failed_session_number=row["session_number"],
        level=row["level"],
        source_titles=source_titles,
    )

    # Insert follow-up session atomically (UPDATE + INSERT in one commit)
    async with aiosqlite.connect(settings.sqlite_path) as db:
        followup = await insert_followup_session(
            db, row["goal_id"], row["session_number"], session_plan
        )
        await db.commit()

    return {"followup_session_added": True, "followup_session": followup}
