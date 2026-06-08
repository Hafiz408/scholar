"""Data access for Super-Agent thread metadata (title/timestamps/count).

Message bodies live in the LangGraph checkpointer; this table only tracks
the lightweight metadata needed to list and label threads.
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.database import get_session
from app.models.db_models import SuperThread, to_dict

_TITLE_MAX = 60


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_title(message: str) -> str:
    title = " ".join(message.strip().split())
    if len(title) > _TITLE_MAX:
        title = title[: _TITLE_MAX - 3] + "..."
    return title


async def get_thread(thread_id: str) -> dict | None:
    """Fetch a single thread's metadata, or None if it doesn't exist."""
    async with get_session() as session:
        obj = await session.get(SuperThread, thread_id)
    return to_dict(obj) if obj is not None else None


async def upsert_thread_on_message(thread_id: str, first_user_message: str) -> None:
    """Create the thread on first message (title from that message), else bump
    message_count and updated_at. Title is set once and never overwritten.

    message_count counts user turns (incremented once per user message), not
    total stored messages."""
    title = _make_title(first_user_message)
    stmt = pg_insert(SuperThread).values(
        thread_id=thread_id,
        title=title,
        message_count=1,
        created_at=_now(),
        updated_at=_now(),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[SuperThread.thread_id],
        set_={
            "message_count": SuperThread.message_count + 1,
            "updated_at": _now(),
        },
    )
    async with get_session() as session:
        await session.execute(stmt)
        await session.commit()


async def list_threads() -> list[dict]:
    """All threads, most-recently-updated first."""
    stmt = select(SuperThread).order_by(SuperThread.updated_at.desc())
    async with get_session() as session:
        rows = (await session.execute(stmt)).scalars().all()
    return [to_dict(r) for r in rows]


async def thread_exists(thread_id: str) -> bool:
    async with get_session() as session:
        result = (
            await session.execute(
                select(SuperThread.thread_id).where(
                    SuperThread.thread_id == thread_id
                )
            )
        ).scalar_one_or_none()
    return result is not None
