import asyncio
import uuid

from app.repositories import super_threads_repo as repo


def test_upsert_creates_then_increments():
    thread_id = str(uuid.uuid4())

    async def _run():
        await repo.upsert_thread_on_message(thread_id, "What is mitosis in detail?")
        first = await repo.list_threads()
        await repo.upsert_thread_on_message(thread_id, "second message")
        second = await repo.list_threads()
        exists = await repo.thread_exists(thread_id)
        missing = await repo.thread_exists("nope-" + uuid.uuid4().hex)
        return first, second, exists, missing

    first, second, exists, missing = asyncio.run(_run())

    f = next(t for t in first if t["thread_id"] == thread_id)
    s = next(t for t in second if t["thread_id"] == thread_id)
    assert f["message_count"] == 1
    assert f["title"] == "What is mitosis in detail?"
    assert s["message_count"] == 2
    assert s["title"] == "What is mitosis in detail?"   # title NOT overwritten
    assert exists is True
    assert missing is False


def test_title_truncated_for_long_first_message():
    thread_id = str(uuid.uuid4())
    long_msg = "x" * 200

    async def _run():
        await repo.upsert_thread_on_message(thread_id, long_msg)
        return await repo.list_threads()

    threads = asyncio.run(_run())
    t = next(t for t in threads if t["thread_id"] == thread_id)
    assert len(t["title"]) <= 60
    assert t["title"].endswith("...")
