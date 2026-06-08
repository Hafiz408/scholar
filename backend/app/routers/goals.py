from datetime import datetime, timezone

from app.core.logging import get_logger
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.agents.orchestrator import create_goal_with_plan, get_goal_plan
from app.agents.notion_mcp import run_notion_export
from app.config import settings
from app.core.database import get_session
from app.models.db_models import StudySession, to_dict
from app.models.schemas import GoalSummary
from app.repositories.goals_repo import list_goals_with_progress

logger = get_logger(__name__)

router = APIRouter(prefix="/goals", tags=["goals"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CreateGoalRequest(BaseModel):
    title: str
    topic: str
    level: str                    # e.g. "beginner", "intermediate", "advanced"
    deadline_days: int
    sessions_per_week: int
    source_ids: list[str]


@router.get("", response_model=list[GoalSummary])
async def list_goals() -> list[dict]:
    """List all study goals with per-goal session progress."""
    return await list_goals_with_progress()


@router.post("", status_code=201)
async def create_goal(body: CreateGoalRequest) -> dict:
    """Create a study goal and generate its session plan via the Planner agent."""
    if body.deadline_days < 1:
        raise HTTPException(status_code=422, detail="deadline_days must be >= 1")
    if body.sessions_per_week < 1:
        raise HTTPException(status_code=422, detail="sessions_per_week must be >= 1")
    if not body.source_ids:
        raise HTTPException(status_code=422, detail="At least one source_id is required")

    result = await create_goal_with_plan(
        title=body.title,
        topic=body.topic,
        level=body.level,
        deadline_days=body.deadline_days,
        sessions_per_week=body.sessions_per_week,
        source_ids=body.source_ids,
    )
    return result


@router.get("/{goal_id}")
async def get_goal(goal_id: str) -> dict:
    """Retrieve a goal and its full ordered session plan."""
    result = await get_goal_plan(goal_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    return result


@router.post("/{goal_id}/adapt")
async def manual_adapt(goal_id: str) -> dict:
    """Manually trigger adaptive replanning for all failed sessions of a goal."""
    # Fetch all completed sessions with quiz_score < 65% for this goal
    async with get_session() as session:
        rows = (
            await session.execute(
                select(StudySession)
                .where(
                    StudySession.goal_id == goal_id,
                    StudySession.status == "complete",
                    StudySession.quiz_score < 0.65,
                )
                .order_by(StudySession.session_number)
            )
        ).scalars().all()

    failed_sessions = [to_dict(r) for r in rows]

    if not failed_sessions:
        return {"followup_sessions_added": 0, "followup_sessions": []}

    added = []
    for sess in failed_sessions:
        try:
            from app.agents.adaptive_planner import handle_quiz_failure
            result = await handle_quiz_failure(sess["id"])
            if result["followup_session_added"]:
                added.append(result["followup_session"])
        except Exception as e:
            logger.error("adapt failed for session %s: %s", sess["id"], e)

    return {"followup_sessions_added": len(added), "followup_sessions": added}


@router.post("/{goal_id}/export/notion")
async def export_to_notion(goal_id: str, background_tasks: BackgroundTasks) -> dict:
    """Export goal study plan and session notes to Notion as a background task."""
    if not settings.notion_api_key:
        raise HTTPException(status_code=400, detail="notion_api_key is not configured")
    if not settings.notion_parent_page_id:
        raise HTTPException(status_code=400, detail="notion_parent_page_id is not configured")
    background_tasks.add_task(
        run_notion_export,
        goal_id,
        settings.notion_api_key,
        settings.notion_parent_page_id,
    )
    return {"status": "export_started"}
