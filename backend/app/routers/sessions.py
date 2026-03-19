import aiosqlite
import json
from fastapi import APIRouter, HTTPException, Request
from sse_starlette import EventSourceResponse
from app.config import settings
from app.agents.note_generator import stream_notes

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("/{session_id}/start")
async def start_session(session_id: str, request: Request):
    """Start a study session — streams notes as SSE notes_chunk events."""
    # Fetch session + goal context
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT ss.id, ss.goal_id, ss.topic, ss.status,
                      sg.level, sg.knowledge_source_ids
               FROM study_sessions ss
               JOIN study_goals sg ON ss.goal_id = sg.id
               WHERE ss.id = ?""",
            (session_id,),
        ) as cur:
            row = await cur.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if row["status"] not in ("pending", "in_progress"):
        raise HTTPException(status_code=409, detail=f"Session status is '{row['status']}' — cannot start")

    source_ids = json.loads(row["knowledge_source_ids"])
    topic = row["topic"]
    level = row["level"]

    async def event_generator():
        async for event in stream_notes(session_id, topic, source_ids, level):
            if await request.is_disconnected():
                break
            yield event

    return EventSourceResponse(event_generator())
