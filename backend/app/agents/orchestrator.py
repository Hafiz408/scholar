import uuid
import json
from datetime import datetime, timezone
from typing import TypedDict
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from sqlalchemy import select, update
from app.core.database import get_session
from app.models.db_models import to_dict, KnowledgeSource, StudyGoal, StudySession
from app.agents.planner import generate_plan, StudyPlanOutput


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ScholarState(TypedDict):
    # Existing fields — do NOT change
    messages: list[dict]
    goal_id: str
    # V2 additions (ORC-01)
    sessions_complete: bool
    weak_session_ids: list[str]
    followup_sessions_added: int
    final_test_id: str | None
    goal_complete: bool


def build_graph(checkpointer: AsyncSqliteSaver):
    """Build minimal LangGraph StateGraph used for AsyncSqliteSaver chat checkpointing."""

    graph = StateGraph(ScholarState)

    # Minimal passthrough node — graph exists for checkpointer, not for routing
    def passthrough(state: ScholarState) -> ScholarState:
        return state

    graph.add_node("chat", passthrough)
    graph.set_entry_point("chat")
    graph.add_edge("chat", END)

    return graph.compile(checkpointer=checkpointer)


async def create_goal_with_plan(
    title: str,
    topic: str,
    level: str,
    deadline_days: int,
    sessions_per_week: int,
    source_ids: list[str],
) -> dict:
    """Create a study goal, generate session plan via Planner agent, persist to Postgres."""
    # Fetch source titles for prompt context
    source_titles: list[str] = []
    if source_ids:
        async with get_session() as session:
            rows = (
                await session.execute(
                    select(KnowledgeSource).where(KnowledgeSource.id.in_(source_ids))
                )
            ).scalars().all()
        source_titles = [row.title for row in rows if row.title is not None]

    # Generate plan via LLM
    plan_output: StudyPlanOutput = await generate_plan(
        goal_title=title,
        topic=topic,
        level=level,
        deadline_days=deadline_days,
        sessions_per_week=sessions_per_week,
        source_titles=source_titles,
    )

    goal_id = str(uuid.uuid4())

    async with get_session() as session:
        # Insert goal
        session.add(
            StudyGoal(
                id=goal_id,
                title=title,
                topic=topic,
                level=level,
                deadline_days=deadline_days,
                sessions_per_week=sessions_per_week,
                knowledge_source_ids=json.dumps(source_ids),
                status="active",
                created_at=_now(),
            )
        )
        # Insert sessions from plan
        for sess in plan_output.sessions:
            session_id = str(uuid.uuid4())
            session.add(
                StudySession(
                    id=session_id,
                    goal_id=goal_id,
                    session_number=sess.session_number,
                    title=sess.title,
                    topic=sess.topic,
                    estimated_minutes=sess.estimated_minutes,
                    status="pending",
                    created_at=_now(),
                )
            )
        await session.commit()

    return {
        "goal_id": goal_id,
        "session_count": len(plan_output.sessions),
        "rationale": plan_output.rationale,
    }


async def update_goal_progress(goal_id: str) -> dict:
    """Return computed progress state for a goal (ORC-02)."""
    async with get_session() as session:
        goal_obj = (
            await session.execute(
                select(StudyGoal).where(StudyGoal.id == goal_id)
            )
        ).scalar_one_or_none()

        sessions = (
            await session.execute(
                select(StudySession)
                .where(StudySession.goal_id == goal_id)
                .order_by(StudySession.session_number)
            )
        ).scalars().all()

    if goal_obj is None:
        return {}

    total = len(sessions)
    completed = sum(1 for s in sessions if s.status == "complete")
    weak_ids = [
        s.id for s in sessions
        if s.quiz_score is not None and s.quiz_score < 0.65
    ]
    return {
        "sessions_complete": total > 0 and completed == total,
        "weak_session_ids": weak_ids,
        "followup_sessions_added": 0,
        "goal_complete": goal_obj.status == "complete",
    }


async def get_goal_plan(goal_id: str) -> dict | None:
    """Retrieve a goal and all its sessions. Data access lives in goals_repo."""
    from app.repositories.goals_repo import get_goal_with_sessions
    return await get_goal_with_sessions(goal_id)
