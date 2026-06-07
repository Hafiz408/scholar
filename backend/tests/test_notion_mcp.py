"""
Tests for Phase 13: Notion MCP Export — NTN-01 through NTN-05.

All tests use monkeypatching — no live Notion API calls.
All tests that touch SQLite use tmp_path for isolation.

Coverage:
    NTN-01 — run_notion_export creates goal parent page + session child pages;
             notion_page_url written back to study_goals row
    NTN-02 — Empty notion_api_key OR notion_parent_page_id → HTTP 400 before any
             background task is enqueued
    NTN-03 — HTTP 429 triggers exponential backoff (asyncio.sleep called with 1, 2);
             all retries exhausted → httpx.HTTPStatusError raised
    NTN-04 — notion_page_url column exists in study_goals SQLite table
    NTN-05 — POST /goals/{id}/export/notion returns {"status": "export_started"}
             immediately (HTTP 200)
"""
import asyncio
import uuid
import pytest
import pytest_asyncio
import aiosqlite
import httpx
from unittest.mock import AsyncMock, MagicMock, patch, call


# ── DB helpers ───────────────────────────────────────────────────────────────

async def _make_db(tmp_path, *, num_sessions=2, notes_markdown="Some notes"):
    """Create a tmp SQLite DB with the Phase 13 schema and seed data.

    Returns (db_path, goal_id).
    """
    db_path = str(tmp_path / "test.sqlite")
    goal_id = str(uuid.uuid4())

    async with aiosqlite.connect(db_path) as db:
        # study_goals table including notion_page_url column
        await db.execute(
            """CREATE TABLE study_goals (
                id TEXT PRIMARY KEY,
                title TEXT,
                topic TEXT,
                level TEXT DEFAULT 'beginner',
                knowledge_source_ids TEXT DEFAULT '[]',
                notion_page_url TEXT
            )"""
        )
        # study_sessions with notes_markdown
        await db.execute(
            """CREATE TABLE study_sessions (
                id TEXT PRIMARY KEY,
                goal_id TEXT,
                session_number INTEGER,
                title TEXT,
                topic TEXT,
                estimated_minutes INTEGER DEFAULT 45,
                status TEXT DEFAULT 'pending',
                quiz_score REAL,
                notes_markdown TEXT,
                created_at TEXT
            )"""
        )
        await db.execute(
            "INSERT INTO study_goals (id, title, topic) VALUES (?, ?, ?)",
            (goal_id, "Test Goal", "Test Topic"),
        )
        for i in range(1, num_sessions + 1):
            await db.execute(
                """INSERT INTO study_sessions
                   (id, goal_id, session_number, title, notes_markdown)
                   VALUES (?, ?, ?, ?, ?)""",
                (str(uuid.uuid4()), goal_id, i, f"Session {i}", notes_markdown),
            )
        await db.commit()

    return db_path, goal_id


def _make_mock_post(fail_times=0):
    """Return an async callable for httpx.AsyncClient.post.

    Simulates returning 429 for the first `fail_times` calls, then 200.
    """
    call_count = 0

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_resp = MagicMock()
        if call_count <= fail_times:
            mock_resp.status_code = 429
            mock_resp.raise_for_status = MagicMock(
                side_effect=httpx.HTTPStatusError(
                    "429 Too Many Requests",
                    request=MagicMock(),
                    response=MagicMock(status_code=429),
                )
            )
        else:
            mock_resp.status_code = 200
            mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"id": "pg-id", "url": "https://notion.so/pg-id"}
        return mock_resp

    return mock_post


# ── NTN-01: run_notion_export creates goal + session pages ───────────────────

@pytest.mark.asyncio
async def test_run_notion_export_creates_goal_and_session_pages(tmp_path, monkeypatch):
    """NTN-01: httpx.AsyncClient.post called 3 times (1 goal + 2 sessions) for 2 sessions."""
    import app.agents.notion_mcp as nm_mod

    db_path, goal_id = await _make_db(tmp_path, num_sessions=2)

    mock_settings = MagicMock()
    mock_settings.sqlite_path = db_path
    monkeypatch.setattr(nm_mod, "settings", mock_settings)

    post_calls = []

    async def mock_post(*args, **kwargs):
        post_calls.append(args)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"id": "pg-id", "url": "https://notion.so/pg-id"}
        return mock_resp

    with patch("app.agents.notion_mcp.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = mock_post
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        await nm_mod.run_notion_export(goal_id, "test-key", "parent-page-id")

    # 1 goal + 2 sessions = 3 total calls
    assert len(post_calls) == 3


@pytest.mark.asyncio
async def test_run_notion_export_writes_notion_page_url(tmp_path, monkeypatch):
    """NTN-01 (writeback): notion_page_url is written back to the study_goals row."""
    import app.agents.notion_mcp as nm_mod

    db_path, goal_id = await _make_db(tmp_path, num_sessions=1)

    mock_settings = MagicMock()
    mock_settings.sqlite_path = db_path
    monkeypatch.setattr(nm_mod, "settings", mock_settings)

    expected_url = "https://notion.so/pg-id"

    async def mock_post(*args, **kwargs):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"id": "pg-id", "url": expected_url}
        return mock_resp

    with patch("app.agents.notion_mcp.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = mock_post
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        await nm_mod.run_notion_export(goal_id, "test-key", "parent-page-id")

    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT notion_page_url FROM study_goals WHERE id = ?", (goal_id,)
        ) as cur:
            row = await cur.fetchone()

    assert row is not None
    assert row[0] == expected_url


@pytest.mark.asyncio
async def test_run_notion_export_null_notes_fallback(tmp_path, monkeypatch):
    """NTN-01 (null notes): Session with notes_markdown=NULL exports without error."""
    import app.agents.notion_mcp as nm_mod

    db_path, goal_id = await _make_db(tmp_path, num_sessions=1, notes_markdown=None)

    mock_settings = MagicMock()
    mock_settings.sqlite_path = db_path
    monkeypatch.setattr(nm_mod, "settings", mock_settings)

    async def mock_post(*args, **kwargs):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"id": "pg-id", "url": "https://notion.so/pg-id"}
        return mock_resp

    with patch("app.agents.notion_mcp.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = mock_post
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        # Should not raise
        await nm_mod.run_notion_export(goal_id, "test-key", "parent-page-id")


# ── NTN-02: Empty api_key or parent_page_id returns HTTP 400 ─────────────────

def test_export_notion_missing_api_key_returns_400(monkeypatch):
    """NTN-02: Empty notion_api_key → HTTP 400, detail contains 'notion_api_key'."""
    from fastapi.testclient import TestClient
    import app.routers.goals as goals_mod

    mock_settings = MagicMock()
    mock_settings.notion_api_key = ""
    mock_settings.notion_parent_page_id = "some-page-id"
    monkeypatch.setattr(goals_mod, "settings", mock_settings)

    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(goals_mod.router)

    client = TestClient(app)
    goal_id = str(uuid.uuid4())
    resp = client.post(f"/goals/{goal_id}/export/notion")

    assert resp.status_code == 400
    assert "notion_api_key" in resp.json()["detail"]


def test_export_notion_missing_parent_page_id_returns_400(monkeypatch):
    """NTN-02: Empty notion_parent_page_id → HTTP 400, detail contains 'notion_parent_page_id'."""
    from fastapi.testclient import TestClient
    import app.routers.goals as goals_mod

    mock_settings = MagicMock()
    mock_settings.notion_api_key = "valid-key"
    mock_settings.notion_parent_page_id = ""
    monkeypatch.setattr(goals_mod, "settings", mock_settings)

    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(goals_mod.router)

    client = TestClient(app)
    goal_id = str(uuid.uuid4())
    resp = client.post(f"/goals/{goal_id}/export/notion")

    assert resp.status_code == 400
    assert "notion_parent_page_id" in resp.json()["detail"]


# ── NTN-03: Backoff retry behavior ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_backoff_retries_before_success(monkeypatch):
    """NTN-03: HTTP 429 twice then 200 — request eventually succeeds without raising."""
    import app.agents.notion_mcp as nm_mod

    async def mock_sleep(secs):
        pass

    monkeypatch.setattr(nm_mod.asyncio, "sleep", mock_sleep)

    call_count = 0

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_resp = MagicMock()
        if call_count <= 2:
            mock_resp.status_code = 429
        else:
            mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"id": "pg-id", "url": "https://notion.so/pg-id"}
        return mock_resp

    client = MagicMock()
    client.post = mock_post

    # Should not raise — third attempt succeeds
    result = await nm_mod._post_with_backoff(
        client,
        "https://api.notion.com/v1/pages",
        {"parent": {"page_id": "test"}},
        {},
    )
    assert result["id"] == "pg-id"


@pytest.mark.asyncio
async def test_backoff_retry_timing(monkeypatch):
    """NTN-03 (backoff timing): asyncio.sleep called with 1 then 2 on 429 retries."""
    import app.agents.notion_mcp as nm_mod

    sleep_calls = []

    async def mock_sleep(secs):
        sleep_calls.append(secs)

    monkeypatch.setattr(nm_mod.asyncio, "sleep", mock_sleep)

    call_count = 0

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_resp = MagicMock()
        if call_count <= 2:
            mock_resp.status_code = 429
        else:
            mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"id": "pg-id", "url": "https://notion.so/pg-id"}
        return mock_resp

    client = MagicMock()
    client.post = mock_post

    result = await nm_mod._post_with_backoff(
        client,
        "https://api.notion.com/v1/pages",
        {"parent": {"page_id": "test"}},
        {},
    )

    # Verify sleep was called with 1 (2**0) then 2 (2**1)
    assert sleep_calls == [1, 2]
    assert result == {"id": "pg-id", "url": "https://notion.so/pg-id"}


@pytest.mark.asyncio
async def test_backoff_exhausted_raises(monkeypatch):
    """NTN-03 (exhausted): All MAX_RETRIES+1 attempts return 429 → HTTPStatusError raised."""
    import app.agents.notion_mcp as nm_mod

    async def mock_sleep(secs):
        pass

    monkeypatch.setattr(nm_mod.asyncio, "sleep", mock_sleep)

    async def mock_post(*args, **kwargs):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "429 Too Many Requests",
                request=MagicMock(),
                response=MagicMock(status_code=429),
            )
        )
        return mock_resp

    client = MagicMock()
    client.post = mock_post

    with pytest.raises(httpx.HTTPStatusError):
        await nm_mod._post_with_backoff(
            client,
            "https://api.notion.com/v1/pages",
            {"parent": {"page_id": "test"}},
            {},
        )


# ── NTN-04: notion_page_url column exists in SQLite schema ───────────────────

@pytest.mark.asyncio
async def test_notion_page_url_column_exists(tmp_path, monkeypatch):
    """NTN-04: init_db() on a fresh SQLite DB includes 'notion_page_url' in study_goals."""
    from app.core.db_schema import init_db
    import app.core.db_schema as db_mod

    db_path = str(tmp_path / "schema_test.sqlite")

    mock_settings = MagicMock()
    mock_settings.sqlite_path = db_path
    monkeypatch.setattr(db_mod, "settings", mock_settings)

    import os
    os.makedirs(str(tmp_path), exist_ok=True)

    init_db()

    async with aiosqlite.connect(db_path) as db:
        async with db.execute("PRAGMA table_info(study_goals)") as cur:
            columns = await cur.fetchall()

    column_names = [col[1] for col in columns]
    assert "notion_page_url" in column_names


# ── NTN-05: POST /goals/{id}/export/notion returns export_started immediately ─

def test_export_notion_returns_export_started(monkeypatch):
    """NTN-05: Valid config → HTTP 200 with {"status": "export_started"}; background not awaited."""
    from fastapi.testclient import TestClient
    import app.routers.goals as goals_mod
    import app.agents.notion_mcp as nm_mod

    mock_settings = MagicMock()
    mock_settings.notion_api_key = "valid-key"
    mock_settings.notion_parent_page_id = "valid-parent-id"
    monkeypatch.setattr(goals_mod, "settings", mock_settings)

    # Prevent actual background task execution during test
    monkeypatch.setattr(nm_mod, "run_notion_export", AsyncMock())

    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(goals_mod.router)

    client = TestClient(app)
    goal_id = str(uuid.uuid4())
    resp = client.post(f"/goals/{goal_id}/export/notion")

    assert resp.status_code == 200
    assert resp.json() == {"status": "export_started"}
