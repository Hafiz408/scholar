import json
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from app.config import settings
from app.core import pg
from app.agents.note_generator import stream_notes

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("/{session_id}")
async def get_session(session_id: str):
    """Return a single study session (used by the study page to render notes/chat/quiz)."""
    async with pg.connect() as db:
        async with db.execute(
            """SELECT id, goal_id, session_number, title, topic, estimated_minutes,
                      status, quiz_score, notes_markdown, created_at
               FROM study_sessions WHERE id = %s""",
            (session_id,),
        ) as cur:
            row = await cur.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return dict(row)


@router.post("/{session_id}/start")
async def start_session(session_id: str, request: Request):
    """Start a study session — streams notes as SSE notes_chunk events."""
    # Fetch session + goal context
    async with pg.connect() as db:
        async with db.execute(
            """SELECT ss.id, ss.goal_id, ss.topic, ss.status,
                      sg.level, sg.knowledge_source_ids
               FROM study_sessions ss
               JOIN study_goals sg ON ss.goal_id = sg.id
               WHERE ss.id = %s""",
            (session_id,),
        ) as cur:
            row = await cur.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if row["status"] not in ("pending", "in_progress"):
        raise HTTPException(status_code=409, detail=f"Session status is '{row['status']}' — cannot start")

    source_ids = json.loads(row["knowledge_source_ids"] or "[]")
    topic = row["topic"]
    level = row["level"]

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
