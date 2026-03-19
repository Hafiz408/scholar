import uuid
import json
import aiosqlite
from typing import TypedDict
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from app.config import settings
from app.agents.planner import generate_plan, StudyPlanOutput


class ScholarState(TypedDict):
    messages: list[dict]
    goal_id: str


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
        async with aiosqlite.connect(settings.sqlite_path) as db:
            db.row_factory = aiosqlite.Row
            placeholders = ",".join("?" * len(source_ids))
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

    async with aiosqlite.connect(settings.sqlite_path) as db:
        # Insert goal — use knowledge_source_ids column (matches SQLite schema)
        await db.execute(
            """INSERT INTO study_goals
               (id, title, topic, level, deadline_days, sessions_per_week, knowledge_source_ids, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'active', datetime('now'))""",
            (goal_id, title, topic, level, deadline_days, sessions_per_week,
             json.dumps(source_ids)),
        )
        # Insert sessions from plan
        for sess in plan_output.sessions:
            session_id = str(uuid.uuid4())
            await db.execute(
                """INSERT INTO study_sessions
                   (id, goal_id, session_number, title, topic, estimated_minutes, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, 'pending', datetime('now'))""",
                (session_id, goal_id, sess.session_number, sess.title,
                 sess.topic, sess.estimated_minutes),
            )
        await db.commit()

    return {
        "goal_id": goal_id,
        "session_count": len(plan_output.sessions),
        "rationale": plan_output.rationale,
    }


async def get_goal_plan(goal_id: str) -> dict | None:
    """Retrieve a goal and all its sessions from SQLite."""
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

    return {
        "goal": dict(goal_row),
        "sessions": [dict(r) for r in session_rows],
    }
