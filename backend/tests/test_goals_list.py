import asyncio
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

from app.config import settings
from app.main import app
from app.models.db_models import StudyGoal, StudySession


def _make_session_factory():
    """Create a fresh async engine + sessionmaker with NullPool.

    NullPool prevents connections from being pooled/reused across event loops,
    which avoids the "Future attached to a different loop" error when each
    asyncio.run() creates a new loop.
    """
    url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(url, poolclass=NullPool, echo=False)
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession), engine


def _seed_goal_with_sessions(goal_id: str, total: int, complete: int) -> None:
    async def _seed():
        factory, engine = _make_session_factory()
        async with factory() as session:
            session.add(
                StudyGoal(
                    id=goal_id,
                    title="List Test Goal",
                    topic="Biology",
                    level="beginner",
                    deadline_days=7,
                    sessions_per_week=1,
                    knowledge_source_ids="[]",
                    status="active",
                    created_at="2026-01-01T00:00:00",
                )
            )
            for n in range(1, total + 1):
                status = "complete" if n <= complete else "pending"
                session.add(
                    StudySession(
                        id=str(uuid.uuid4()),
                        goal_id=goal_id,
                        session_number=n,
                        title="S",
                        topic="T",
                        estimated_minutes=30,
                        status=status,
                        created_at="2026-01-01T00:00:00",
                    )
                )
            await session.commit()
        await engine.dispose()

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


def test_get_goal_plan_still_returns_goal_and_sessions():
    goal_id = str(uuid.uuid4())
    _seed_goal_with_sessions(goal_id, total=3, complete=1)
    with TestClient(app) as client:
        res = client.get(f"/goals/{goal_id}")
    assert res.status_code == 200
    body = res.json()
    assert body["goal"]["id"] == goal_id
    assert len(body["sessions"]) == 3
