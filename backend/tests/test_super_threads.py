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


import uuid as _uuid

from fastapi.testclient import TestClient

from app.main import app


def test_list_threads_endpoint_returns_recorded_thread():
    thread_id = str(_uuid.uuid4())

    async def _seed():
        await repo.upsert_thread_on_message(thread_id, "endpoint list test")

    asyncio.run(_seed())

    with TestClient(app) as client:
        res = client.get("/super/threads")

    assert res.status_code == 200
    threads = res.json()
    assert any(t["thread_id"] == thread_id for t in threads)
    mine = next(t for t in threads if t["thread_id"] == thread_id)
    assert mine["title"] == "endpoint list test"
    assert mine["message_count"] == 1


def test_get_thread_detail_unknown_returns_404():
    with TestClient(app) as client:
        res = client.get(f"/super/threads/unknown-{_uuid.uuid4().hex}")
    assert res.status_code == 404


def test_get_thread_detail_known_returns_messages_list():
    thread_id = str(_uuid.uuid4())

    async def _seed():
        await repo.upsert_thread_on_message(thread_id, "detail test")

    asyncio.run(_seed())

    with TestClient(app) as client:
        res = client.get(f"/super/threads/{thread_id}")

    assert res.status_code == 200
    body = res.json()
    assert body["thread_id"] == thread_id
    assert body["title"] == "detail test"
    assert isinstance(body["messages"], list)
