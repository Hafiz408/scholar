from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.agents.orchestrator import create_goal_with_plan, get_goal_plan

router = APIRouter(prefix="/goals", tags=["goals"])


class CreateGoalRequest(BaseModel):
    title: str
    topic: str
    level: str                    # e.g. "beginner", "intermediate", "advanced"
    deadline_days: int
    sessions_per_week: int
    source_ids: list[str]


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
