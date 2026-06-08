import json
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.config import settings
from app.core.database import get_session
from app.models.db_models import StudySession, StudyGoal, to_dict
from app.agents.session_chat import stream_chat

router = APIRouter(prefix="/sessions", tags=["chat"])


class ChatMessageRequest(BaseModel):
    message: str


@router.post("/{session_id}/chat")
async def chat_in_session(
    session_id: str,
    body: ChatMessageRequest,
    request: Request,
):
    """Send a chat message — streams token/citations/done SSE events."""
    async with get_session() as session:
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

    goal_id = sess_obj.goal_id
    source_ids = json.loads(goal_obj.knowledge_source_ids or "[]")
    checkpointer = request.app.state.checkpointer

    async def event_generator():
        async for event in stream_chat(
            session_id=session_id,
            goal_id=goal_id,
            message=body.message,
            source_ids=source_ids,
            checkpointer=checkpointer,
        ):
            if await request.is_disconnected():
                break
            yield event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
