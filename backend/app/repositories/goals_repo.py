"""Data access for study goals. Centralizes ORM queries (SQLAlchemy 2.0 async)."""
from sqlalchemy import case, func, select

from app.core.database import get_session
from app.models.db_models import StudyGoal, StudySession, to_dict


async def list_goals_with_progress() -> list[dict]:
    """All goals, newest first, each annotated with total/completed session counts."""
    stmt = (
        select(
            StudyGoal.id,
            StudyGoal.title,
            StudyGoal.topic,
            StudyGoal.level,
            StudyGoal.status,
            StudyGoal.created_at,
            StudyGoal.deadline_days,
            func.count(StudySession.id).label("total_sessions"),
            func.coalesce(
                func.sum(case((StudySession.status == "complete", 1), else_=0)), 0
            ).label("completed_sessions"),
        )
        .select_from(StudyGoal)
        .join(StudySession, StudySession.goal_id == StudyGoal.id, isouter=True)
        .group_by(StudyGoal.id)
        .order_by(StudyGoal.created_at.desc())
    )
    async with get_session() as session:
        rows = (await session.execute(stmt)).mappings().all()
    return [dict(r) for r in rows]


async def get_goal_with_sessions(goal_id: str) -> dict | None:
    """A single goal plus its ordered sessions, or None if the goal is missing."""
    async with get_session() as session:
        goal_obj = await session.get(StudyGoal, goal_id)
        if goal_obj is None:
            return None

        stmt = (
            select(StudySession)
            .where(StudySession.goal_id == goal_id)
            .order_by(StudySession.session_number)
        )
        session_rows = (await session.execute(stmt)).scalars().all()

    return {
        "goal": to_dict(goal_obj),
        "sessions": [to_dict(s) for s in session_rows],
    }
