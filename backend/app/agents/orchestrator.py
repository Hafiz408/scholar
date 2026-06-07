import uuid
import json
from typing import TypedDict
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from app.core import pg
from app.agents.planner import generate_plan, StudyPlanOutput


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
    """Create a study goal, generate session plan via Planner agent, persist to SQLite."""
    # Fetch source titles for prompt context
    source_titles: list[str] = []
    if source_ids:
        async with pg.connect() as db:
            placeholders = ",".join(["%s"] * len(source_ids))
            async with db.execute(
                f"SELECT id, title FROM knowledge_sources WHERE id IN ({placeholders})",
                source_ids,
            ) as cur:
                rows = await cur.fetchall()
        source_titles = [row["title"] for row in rows]

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

    async with pg.connect() as db:
        # Insert goal — use knowledge_source_ids column (matches schema)
        await db.execute(
            """INSERT INTO study_goals
               (id, title, topic, level, deadline_days, sessions_per_week, knowledge_source_ids, status, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, 'active', now()::text)""",
            (goal_id, title, topic, level, deadline_days, sessions_per_week,
             json.dumps(source_ids)),
        )
        # Insert sessions from plan
        for sess in plan_output.sessions:
            session_id = str(uuid.uuid4())
            await db.execute(
                """INSERT INTO study_sessions
                   (id, goal_id, session_number, title, topic, estimated_minutes, status, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, 'pending', now()::text)""",
                (session_id, goal_id, sess.session_number, sess.title,
                 sess.topic, sess.estimated_minutes),
            )
        await db.commit()

    return {
        "goal_id": goal_id,
        "session_count": len(plan_output.sessions),
        "rationale": plan_output.rationale,
    }


async def update_goal_progress(goal_id: str) -> dict:
    """Return computed progress state for a goal (ORC-02)."""
    async with pg.connect() as db:
        async with db.execute(
            "SELECT status FROM study_goals WHERE id=%s", (goal_id,)
        ) as cur:
            goal = await cur.fetchone()
        async with db.execute(
            "SELECT id, status, quiz_score FROM study_sessions WHERE goal_id=%s ORDER BY session_number",
            (goal_id,),
        ) as cur:
            sessions = await cur.fetchall()
    if goal is None:
        return {}
    total = len(sessions)
    completed = sum(1 for s in sessions if s["status"] == "complete")
    weak_ids = [
        s["id"] for s in sessions
        if s["quiz_score"] is not None and s["quiz_score"] < 0.65
    ]
    return {
        "sessions_complete": total > 0 and completed == total,
        "weak_session_ids": weak_ids,
        "followup_sessions_added": 0,
        "goal_complete": goal["status"] == "complete",
    }


async def get_goal_plan(goal_id: str) -> dict | None:
    """Retrieve a goal and all its sessions. Data access lives in goals_repo."""
    from app.repositories.goals_repo import get_goal_with_sessions
    return await get_goal_with_sessions(goal_id)
