import json
import asyncio
from app.core.logging import get_logger
import aiosqlite
from app.config import settings
from app.llm_factory import get_llm
from app.agents.prompts import NOTE_SYSTEM_PROMPT
from app.retrieval.hybrid_retriever import retrieve

logger = get_logger(__name__)


def _format_context(chunks) -> str:
    """Format RetrievedChunk list into a numbered context block with citations."""
    parts = []
    for i, chunk in enumerate(chunks, 1):
        source = getattr(chunk, "source_title", "Unknown Source")
        page = getattr(chunk, "page_number", "?")
        parts.append(f"[{i}] (Source: {source}, p.{page})\n{chunk.content}")
    return "\n\n".join(parts)


async def stream_notes(
    session_id: str,
    topic: str,
    source_ids: list[str],
    level: str,
):
    """Async generator yielding SSE-formatted strings for note generation."""
    try:
        retrieval = await retrieve(topic, source_ids, top_k=8)
        context = _format_context(retrieval.chunks)

        llm = get_llm(temperature=0, streaming=True)
        messages = [
            {"role": "system", "content": NOTE_SYSTEM_PROMPT.format(level=level)},
            {"role": "user", "content": f"Topic: {topic}\n\nContext:\n{context}"},
        ]

        full_notes: list[str] = []
        async for chunk in llm.astream(messages):
            token = chunk.content
            if token:
                full_notes.append(token)
                payload = json.dumps({"type": "notes_chunk", "content": token})
                yield f"event: notes_chunk\ndata: {payload}\n\n"

        notes_markdown = "".join(full_notes)

        # Persist to SQLite — update session status to in_progress and save notes
        async with aiosqlite.connect(settings.sqlite_path) as db:
            await db.execute(
                "UPDATE study_sessions SET notes_markdown=?, status=? WHERE id=?",
                (notes_markdown, "in_progress", session_id),
            )
            await db.commit()

        done_payload = json.dumps({
            "type": "notes_done",
            "total_chars": len(notes_markdown),
        })
        yield f"event: notes_done\ndata: {done_payload}\n\n"

    except asyncio.CancelledError:
        # Client disconnected — clean exit, no re-raise needed for SSE generators
        return
    except Exception as exc:
        logger.exception("Notes stream failed for session %s", session_id)
        payload = json.dumps({"type": "error", "content": str(exc)})
        yield f"event: error\ndata: {payload}\n\n"
