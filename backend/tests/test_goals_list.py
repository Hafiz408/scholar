import asyncio
import uuid

import aiosqlite
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def _seed_goal_with_sessions(goal_id: str, total: int, complete: int) -> None:
    async def _seed():
        async with aiosqlite.connect(settings.sqlite_path) as db:
            await db.execute(
                """INSERT INTO study_goals
                   (id, title, topic, level, deadline_days, sessions_per_week,
                    knowledge_source_ids, status, created_at)
                   VALUES (?, 'List Test Goal', 'Biology', 'beginner', 7, 1, '[]',
                           'active', datetime('now'))""",
                (goal_id,),
            )
            for n in range(1, total + 1):
                status = "complete" if n <= complete else "pending"
                await db.execute(
                    """INSERT INTO study_sessions
                       (id, goal_id, session_number, title, topic, estimated_minutes,
                        status, created_at)
                       VALUES (?, ?, ?, 'S', 'T', 30, ?, datetime('now'))""",
                    (str(uuid.uuid4()), goal_id, n, status),
                )
            await db.commit()

    asyncio.run(_seed())


def test_list_goals_includes_progress():
    goal_id = str(uuid.uuid4())
    _seed_goal_with_sessions(goal_id, total=4, complete=2)

    with TestClient(app) as client:
        res = client.get("/goals")

    assert res.status_code == 200
    goals = res.json()
    assert isinstance(goals, list)
    ours = next((g for g in goals if g["id"] == goal_id), None)
    assert ours is not None
    assert ours["total_sessions"] == 4
    assert ours["completed_sessions"] == 2
    assert ours["title"] == "List Test Goal"


def test_list_goals_no_redirect_no_trailing_slash():
    with TestClient(app) as client:
        res = client.get("/goals", follow_redirects=False)
    assert res.status_code == 200
