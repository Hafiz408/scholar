from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from fastapi.responses import StreamingResponse
from app.agents.super_agent import stream_super_chat
from app.models.schemas import SuperThreadDetail, SuperThreadSummary
from app.repositories.super_threads_repo import list_threads, get_thread, upsert_thread_on_message

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

    # Record/refresh thread metadata so it appears in GET /super/threads.
    await upsert_thread_on_message(body.thread_id, body.message)

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


@router.get("/threads", response_model=list[SuperThreadSummary])
async def get_super_threads() -> list[dict]:
    """List all super-agent threads, most recently updated first."""
    return await list_threads()


@router.get("/threads/{thread_id}", response_model=SuperThreadDetail)
async def get_super_thread(thread_id: str, request: Request) -> dict:
    """Load a thread's title and message history (messages from the checkpointer)."""
    meta = await get_thread(thread_id)

    checkpointer = request.app.state.checkpointer
    config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
    checkpoint_tuple = await checkpointer.aget_tuple(config)

    if meta is None and checkpoint_tuple is None:
        raise HTTPException(status_code=404, detail="Thread not found")

    messages: list[dict] = []
    if checkpoint_tuple and checkpoint_tuple.checkpoint:
        state_messages = (
            checkpoint_tuple.checkpoint.get("channel_values", {}).get("messages", [])
        )
        for m in state_messages:
            if isinstance(m, dict) and "role" in m and "content" in m:
                messages.append({"role": m["role"], "content": m["content"]})

    return {
        "thread_id": thread_id,
        "title": meta["title"] if meta else None,
        "messages": messages,
    }
