import json
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
from app.config import settings
from app.core import pg
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
    async with pg.connect() as db:
        async with db.execute(
            """SELECT ss.id, ss.goal_id, ss.status,
                      sg.knowledge_source_ids
               FROM study_sessions ss
               JOIN study_goals sg ON ss.goal_id = sg.id
               WHERE ss.id = %s""",
            (session_id,),
        ) as cur:
            row = await cur.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")

    goal_id = row["goal_id"]
    source_ids = json.loads(row["knowledge_source_ids"] or "[]")
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
