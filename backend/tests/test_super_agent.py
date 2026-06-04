"""
Tests for Phase 12: Super Agent — SUP-01 through SUP-04.

All external calls are mocked — no live LLM, no live database.

Coverage:
    SUP-01  — stream_super_chat() passes all ready source_ids to retrieve()
    SUP-02  — empty knowledge base yields SSE error "No books indexed yet", retrieve not called
    SUP-03  — thread_id from request passed unchanged to checkpointer.aput
    SUP-04  — SSE event sequence: token(s) → citations → done, with correct JSON shapes
    ROUTER  — POST /super/chat/stream returns 200 on valid payload
    ROUTER  — POST /super/chat/stream returns 422 on empty thread_id
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call


# ── Helpers ──────────────────────────────────────────────────────────────────

async def collect(gen):
    """Drain an async generator and return all items as a list."""
    results = []
    async for item in gen:
        results.append(item)
    return results


def _make_aiosqlite_mock(rows):
    """Return a mock that satisfies `async with aiosqlite.connect(...) as db:` usage.

    The super_agent does:
        async with aiosqlite.connect(path) as db:
            async with db.execute(sql) as cur:
                rows = await cur.fetchall()

    We need two nested async context managers.
    """
    mock_cursor = AsyncMock()
    mock_cursor.fetchall = AsyncMock(return_value=rows)

    # inner async context manager: db.execute(...)
    mock_cursor_cm = MagicMock()
    mock_cursor_cm.__aenter__ = AsyncMock(return_value=mock_cursor)
    mock_cursor_cm.__aexit__ = AsyncMock(return_value=False)

    mock_db = MagicMock()
    mock_db.execute = MagicMock(return_value=mock_cursor_cm)

    # outer async context manager: aiosqlite.connect(...)
    mock_connect_cm = MagicMock()
    mock_connect_cm.__aenter__ = AsyncMock(return_value=mock_db)
    mock_connect_cm.__aexit__ = AsyncMock(return_value=False)

    mock_connect = MagicMock(return_value=mock_connect_cm)
    return mock_connect


def _make_retrieve_mock(chunks=None, strategy_used="hybrid", latency_ms=10):
    """Return an AsyncMock for retrieve() returning a result with .chunks."""
    if chunks is None:
        chunks = []
    mock_result = MagicMock()
    mock_result.chunks = chunks
    mock_result.strategy_used = strategy_used
    mock_result.latency_ms = latency_ms
    return AsyncMock(return_value=mock_result)


def _make_llm_mock(tokens=("Hello", " world")):
    """Return a mock for get_llm() whose .astream() yields token chunks."""
    async def fake_astream(messages):
        for token in tokens:
            chunk = MagicMock()
            chunk.content = token
            yield chunk

    mock_llm = MagicMock()
    mock_llm.astream = fake_astream
    return mock_llm


def _make_checkpointer_mock():
    """Return an AsyncMock checkpointer with aget_tuple→None and aput as AsyncMock."""
    mock_cp = AsyncMock()
    mock_cp.aget_tuple = AsyncMock(return_value=None)
    mock_cp.aput = AsyncMock(return_value=None)
    return mock_cp


# ── SUP-01: All-sources retrieval ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sup01_retrieve_called_with_all_source_ids():
    """SUP-01: retrieve() is called with source_ids from all ready knowledge sources."""
    rows = [("source_id_a",), ("source_id_b",)]
    mock_connect = _make_aiosqlite_mock(rows)
    mock_retrieve = _make_retrieve_mock()
    mock_llm = _make_llm_mock()
    mock_cp = _make_checkpointer_mock()

    with patch("app.agents.super_agent.aiosqlite.connect", mock_connect), \
         patch("app.agents.super_agent.retrieve", mock_retrieve), \
         patch("app.agents.super_agent.get_llm", return_value=mock_llm):
        from app.agents.super_agent import stream_super_chat
        await collect(stream_super_chat(
            message="test",
            thread_id="uuid-1",
            checkpointer=mock_cp,
        ))

    mock_retrieve.assert_called_once()
    call_kwargs = mock_retrieve.call_args
    # retrieve(message, source_ids, top_k=8)
    positional_source_ids = call_kwargs[0][1] if len(call_kwargs[0]) > 1 else call_kwargs[1].get("source_ids")
    assert set(positional_source_ids) == {"source_id_a", "source_id_b"}


# ── SUP-02: Empty knowledge base ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sup02_empty_kb_yields_error_event():
    """SUP-02: empty source list yields a single SSE error event with 'No books indexed yet'."""
    mock_connect = _make_aiosqlite_mock([])  # no rows
    mock_retrieve = _make_retrieve_mock()
    mock_cp = _make_checkpointer_mock()

    with patch("app.agents.super_agent.aiosqlite.connect", mock_connect), \
         patch("app.agents.super_agent.retrieve", mock_retrieve):
        from app.agents.super_agent import stream_super_chat
        events = await collect(stream_super_chat(
            message="test",
            thread_id="uuid-1",
            checkpointer=mock_cp,
        ))

    assert len(events) == 1
    assert events[0].startswith("event: error\n")
    data_line = [line for line in events[0].split("\n") if line.startswith("data:")][0]
    payload = json.loads(data_line[len("data: "):])
    assert payload["content"] == "No books indexed yet"


@pytest.mark.asyncio
async def test_sup02_retrieve_not_called_when_empty_kb():
    """SUP-02: retrieve() must NOT be called when source list is empty."""
    mock_connect = _make_aiosqlite_mock([])
    mock_retrieve = _make_retrieve_mock()
    mock_cp = _make_checkpointer_mock()

    with patch("app.agents.super_agent.aiosqlite.connect", mock_connect), \
         patch("app.agents.super_agent.retrieve", mock_retrieve):
        from app.agents.super_agent import stream_super_chat
        await collect(stream_super_chat(
            message="test",
            thread_id="uuid-1",
            checkpointer=mock_cp,
        ))

    mock_retrieve.assert_not_called()


# ── SUP-03: thread_id passthrough ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sup03_thread_id_passed_unchanged_to_checkpointer():
    """SUP-03: thread_id from request is passed unchanged to checkpointer.aput config."""
    rows = [("source_id_x",)]
    mock_connect = _make_aiosqlite_mock(rows)
    mock_retrieve = _make_retrieve_mock()
    mock_llm = _make_llm_mock()
    mock_cp = _make_checkpointer_mock()

    frontend_thread_id = "my-frontend-uuid"

    with patch("app.agents.super_agent.aiosqlite.connect", mock_connect), \
         patch("app.agents.super_agent.retrieve", mock_retrieve), \
         patch("app.agents.super_agent.get_llm", return_value=mock_llm):
        from app.agents.super_agent import stream_super_chat
        await collect(stream_super_chat(
            message="hi",
            thread_id=frontend_thread_id,
            checkpointer=mock_cp,
        ))

    mock_cp.aput.assert_called_once()
    aput_call = mock_cp.aput.call_args
    # aput(config, checkpoint, metadata, channel_versions)
    config_arg = aput_call[0][0] if len(aput_call[0]) > 0 else aput_call[1].get("config")
    # thread_id must pass through unchanged; checkpoint_ns is required by AsyncSqliteSaver.aput().
    assert config_arg["configurable"]["thread_id"] == frontend_thread_id
    assert config_arg["configurable"].get("checkpoint_ns") == ""


# ── SUP-04: SSE event format parity ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_sup04_sse_event_sequence():
    """SUP-04: SSE event sequence is token(s) → citations → done."""
    rows = [("source_id_y",)]
    mock_connect = _make_aiosqlite_mock(rows)
    mock_retrieve = _make_retrieve_mock()
    mock_llm = _make_llm_mock(tokens=("Hello", " world"))
    mock_cp = _make_checkpointer_mock()

    with patch("app.agents.super_agent.aiosqlite.connect", mock_connect), \
         patch("app.agents.super_agent.retrieve", mock_retrieve), \
         patch("app.agents.super_agent.get_llm", return_value=mock_llm):
        from app.agents.super_agent import stream_super_chat
        events = await collect(stream_super_chat(
            message="test",
            thread_id="test-thread",
            checkpointer=mock_cp,
        ))

    event_types = []
    for event_str in events:
        for line in event_str.split("\n"):
            if line.startswith("event:"):
                event_types.append(line.split(":", 1)[1].strip())

    # Must contain at least one token, then citations, then done
    assert "token" in event_types
    assert "citations" in event_types
    assert "done" in event_types

    # token must come before citations, citations before done
    last_token_idx = max(i for i, t in enumerate(event_types) if t == "token")
    citations_idx = event_types.index("citations")
    done_idx = event_types.index("done")
    assert last_token_idx < citations_idx < done_idx


@pytest.mark.asyncio
async def test_sup04_token_event_json_shape():
    """SUP-04: token events have JSON with keys 'type' and 'content'."""
    rows = [("source_id_z",)]
    mock_connect = _make_aiosqlite_mock(rows)
    mock_retrieve = _make_retrieve_mock()
    mock_llm = _make_llm_mock(tokens=("Hello",))
    mock_cp = _make_checkpointer_mock()

    with patch("app.agents.super_agent.aiosqlite.connect", mock_connect), \
         patch("app.agents.super_agent.retrieve", mock_retrieve), \
         patch("app.agents.super_agent.get_llm", return_value=mock_llm):
        from app.agents.super_agent import stream_super_chat
        events = await collect(stream_super_chat(
            message="test",
            thread_id="test-thread",
            checkpointer=mock_cp,
        ))

    token_events = [e for e in events if e.startswith("event: token\n")]
    assert len(token_events) >= 1
    for event_str in token_events:
        data_line = [l for l in event_str.split("\n") if l.startswith("data:")][0]
        payload = json.loads(data_line[len("data: "):])
        assert "type" in payload
        assert "content" in payload


@pytest.mark.asyncio
async def test_sup04_citations_event_json_shape():
    """SUP-04: citations event has JSON with keys 'type' and 'chunks'."""
    rows = [("source_id_z",)]
    mock_connect = _make_aiosqlite_mock(rows)
    mock_retrieve = _make_retrieve_mock()
    mock_llm = _make_llm_mock(tokens=("Hello",))
    mock_cp = _make_checkpointer_mock()

    with patch("app.agents.super_agent.aiosqlite.connect", mock_connect), \
         patch("app.agents.super_agent.retrieve", mock_retrieve), \
         patch("app.agents.super_agent.get_llm", return_value=mock_llm):
        from app.agents.super_agent import stream_super_chat
        events = await collect(stream_super_chat(
            message="test",
            thread_id="test-thread",
            checkpointer=mock_cp,
        ))

    citations_events = [e for e in events if e.startswith("event: citations\n")]
    assert len(citations_events) == 1
    data_line = [l for l in citations_events[0].split("\n") if l.startswith("data:")][0]
    payload = json.loads(data_line[len("data: "):])
    assert "type" in payload
    assert "chunks" in payload


@pytest.mark.asyncio
async def test_sup04_done_event_json_shape():
    """SUP-04: done event has JSON with keys 'type', 'strategy_used', 'latency_ms'."""
    rows = [("source_id_z",)]
    mock_connect = _make_aiosqlite_mock(rows)
    mock_retrieve = _make_retrieve_mock(strategy_used="hybrid", latency_ms=42)
    mock_llm = _make_llm_mock(tokens=("Hello",))
    mock_cp = _make_checkpointer_mock()

    with patch("app.agents.super_agent.aiosqlite.connect", mock_connect), \
         patch("app.agents.super_agent.retrieve", mock_retrieve), \
         patch("app.agents.super_agent.get_llm", return_value=mock_llm):
        from app.agents.super_agent import stream_super_chat
        events = await collect(stream_super_chat(
            message="test",
            thread_id="test-thread",
            checkpointer=mock_cp,
        ))

    done_events = [e for e in events if e.startswith("event: done\n")]
    assert len(done_events) == 1
    data_line = [l for l in done_events[0].split("\n") if l.startswith("data:")][0]
    payload = json.loads(data_line[len("data: "):])
    assert "type" in payload
    assert "strategy_used" in payload
    assert "latency_ms" in payload


# ── Router: POST /super/chat/stream ──────────────────────────────────────────

def test_router_returns_200_on_valid_payload():
    """ROUTER: valid POST returns HTTP 200 with SSE body."""
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from app.routers.super import router

    canned_events = [
        "event: token\ndata: {\"type\": \"token\", \"content\": \"hi\"}\n\n",
        "event: done\ndata: {\"type\": \"done\", \"strategy_used\": \"hybrid\", \"latency_ms\": 5}\n\n",
    ]

    async def fake_stream(**kwargs):
        for ev in canned_events:
            yield ev

    test_app = FastAPI()
    test_app.include_router(router)

    with patch("app.routers.super.stream_super_chat", side_effect=fake_stream):
        # Attach a dummy checkpointer to app.state
        with TestClient(test_app, raise_server_exceptions=True) as client:
            client.app.state.checkpointer = MagicMock()
            response = client.post(
                "/super/chat/stream",
                json={"message": "hello", "thread_id": "test-uuid"},
            )

    assert response.status_code == 200
    body = response.text
    for ev in canned_events:
        assert ev.strip() in body or "token" in body or "done" in body


def test_router_returns_422_on_empty_thread_id():
    """ROUTER: empty thread_id is rejected with HTTP 422 (Pydantic validation)."""
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from app.routers.super import router

    test_app = FastAPI()
    test_app.include_router(router)

    with TestClient(test_app, raise_server_exceptions=True) as client:
        client.app.state.checkpointer = MagicMock()
        response = client.post(
            "/super/chat/stream",
            json={"message": "hello", "thread_id": ""},
        )

    assert response.status_code == 422
