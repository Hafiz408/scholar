from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from fastapi.responses import StreamingResponse
from app.agents.super_agent import stream_super_chat

router = APIRouter(prefix="/super", tags=["super"])


class SuperChatRequest(BaseModel):
    message: str
    thread_id: str = Field(min_length=1)  # UUID from frontend localStorage — server never generates this


@router.post("/chat/stream")
async def super_chat_stream(body: SuperChatRequest, request: Request):
    """Stream a super-agent chat response grounded in ALL ready knowledge sources.

    Accepts {message, thread_id} and returns SSE token/citations/done events.
    thread_id must be a non-empty UUID provided by the frontend (from localStorage).
    """
    checkpointer = request.app.state.checkpointer

    async def event_generator():
        async for event in stream_super_chat(
            message=body.message,
            thread_id=body.thread_id,
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
