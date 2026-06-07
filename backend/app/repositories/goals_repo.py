"""Data access for study goals. Centralizes raw aiosqlite queries."""
import aiosqlite

from app.config import settings


async def list_goals_with_progress() -> list[dict]:
    """All goals, newest first, each annotated with total/completed session counts."""
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT g.id, g.title, g.topic, g.level, g.status,
                   g.created_at, g.deadline_days,
                   COUNT(s.id) AS total_sessions,
                   COALESCE(SUM(CASE WHEN s.status = 'complete' THEN 1 ELSE 0 END), 0)
                       AS completed_sessions
            FROM study_goals g
            LEFT JOIN study_sessions s ON s.goal_id = g.id
            GROUP BY g.id
            ORDER BY g.created_at DESC
            """
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_goal_with_sessions(goal_id: str) -> dict | None:
    """A single goal plus its ordered sessions, or None if the goal is missing."""
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM study_goals WHERE id = ?", (goal_id,)
        ) as cur:
            goal_row = await cur.fetchone()
        if goal_row is None:
            return None
        async with db.execute(
            "SELECT * FROM study_sessions WHERE goal_id = ? ORDER BY session_number",
            (goal_id,),
        ) as cur:
            session_rows = await cur.fetchall()
    return {"goal": dict(goal_row), "sessions": [dict(r) for r in session_rows]}
