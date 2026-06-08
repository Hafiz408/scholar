import json
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.config import settings
from app.core.database import get_session as get_db_session
from app.models.db_models import StudySession, StudyGoal, to_dict
from app.agents.note_generator import stream_notes

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("/{session_id}")
async def get_session(session_id: str):
    """Return a single study session (used by the study page to render notes/chat/quiz)."""
    async with get_db_session() as session:
        obj = (
            await session.execute(
                select(StudySession).where(StudySession.id == session_id)
            )
        ).scalar_one_or_none()

    if obj is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return to_dict(obj)


@router.post("/{session_id}/start")
async def start_session(session_id: str, request: Request):
    """Start a study session — streams notes as SSE notes_chunk events."""
    # Fetch session + goal context via join
    async with get_db_session() as session:
        result = (
            await session.execute(
                select(StudySession, StudyGoal)
                .join(StudyGoal, StudySession.goal_id == StudyGoal.id)
                .where(StudySession.id == session_id)
            )
        ).one_or_none()

    if result is None:
        raise HTTPException(status_code=404, detail="Session not found")

    sess_obj, goal_obj = result

    if sess_obj.status not in ("pending", "in_progress"):
        raise HTTPException(status_code=409, detail=f"Session status is '{sess_obj.status}' — cannot start")

    source_ids = json.loads(goal_obj.knowledge_source_ids or "[]")
    topic = sess_obj.topic
    level = goal_obj.level

    async def event_generator():
        async for event in stream_notes(session_id, topic, source_ids, level):
            if await request.is_disconnected():
                break
            yield event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
