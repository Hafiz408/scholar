import asyncio
import uuid

from fastapi.testclient import TestClient

from app.main import app
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


def test_list_threads_endpoint_returns_recorded_thread():
    thread_id = str(uuid.uuid4())

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
        res = client.get(f"/super/threads/unknown-{uuid.uuid4().hex}")
    assert res.status_code == 404


def test_get_thread_detail_known_returns_messages_list():
    thread_id = str(uuid.uuid4())

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


def test_get_thread_detail_extracts_checkpoint_messages():
    thread_id = str(uuid.uuid4())

    async def _seed_meta():
        await repo.upsert_thread_on_message(thread_id, "checkpoint extraction test")

    asyncio.run(_seed_meta())

    with TestClient(app) as client:
        # Write a checkpoint with real messages, mirroring super_agent.py's aput shape.
        async def _write_checkpoint():
            checkpointer = app.state.checkpointer
            config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
            messages = [
                {"role": "user", "content": "hello agent"},
                {"role": "assistant", "content": "hello human"},
            ]
            # Build new_checkpoint exactly like super_agent.py does.
            new_checkpoint = {
                "v": 1,
                "id": "test-ckpt-1",
                "ts": "",
                "channel_values": {"messages": messages},
                "channel_versions": {},
                "versions_seen": {},
                "pending_sends": [],
            }
            metadata = {"source": "update", "step": len(messages), "writes": {}}
            await checkpointer.aput(config, new_checkpoint, metadata, {})

        asyncio.run(_write_checkpoint())

        res = client.get(f"/super/threads/{thread_id}")

    assert res.status_code == 200
    body = res.json()
    roles = [m["role"] for m in body["messages"]]
    contents = [m["content"] for m in body["messages"]]
    assert "user" in roles and "assistant" in roles
    assert "hello agent" in contents
    assert "hello human" in contents
