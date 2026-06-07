"""Data access for Super-Agent thread metadata (title/timestamps/count).

Message bodies live in the LangGraph checkpointer; this table only tracks
the lightweight metadata needed to list and label threads.
"""
import aiosqlite

from app.config import settings

_TITLE_MAX = 60


def _make_title(message: str) -> str:
    title = " ".join(message.strip().split())
    if len(title) > _TITLE_MAX:
        title = title[: _TITLE_MAX - 3] + "..."
    return title


async def upsert_thread_on_message(thread_id: str, first_user_message: str) -> None:
    """Create the thread on first message (title from that message), else bump
    message_count and updated_at. Title is set once and never overwritten."""
    title = _make_title(first_user_message)
    async with aiosqlite.connect(settings.sqlite_path) as db:
        await db.execute(
            """
            INSERT INTO super_threads
                (thread_id, title, message_count, created_at, updated_at)
            VALUES (?, ?, 1, datetime('now'), datetime('now'))
            ON CONFLICT(thread_id) DO UPDATE SET
                message_count = message_count + 1,
                updated_at = datetime('now')
            """,
            (thread_id, title),
        )
        await db.commit()


async def list_threads() -> list[dict]:
    """All threads, most-recently-updated first."""
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT thread_id, title, message_count, created_at, updated_at
               FROM super_threads ORDER BY updated_at DESC"""
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def thread_exists(thread_id: str) -> bool:
    async with aiosqlite.connect(settings.sqlite_path) as db:
        async with db.execute(
            "SELECT 1 FROM super_threads WHERE thread_id = ?", (thread_id,)
        ) as cur:
            return await cur.fetchone() is not None
