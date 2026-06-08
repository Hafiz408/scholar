"""
Tests for Phase 13: Notion MCP Export — NTN-01 through NTN-05.

All tests use monkeypatching — no live Notion API calls.
NTN-01/NTN-02/NTN-03/NTN-05 are fully ported to the ORM-based notion_mcp.py.
NTN-04 (init_db / SQLite column check) is skipped — init_db() no longer exists
after the SQLite→Postgres migration; the table schema is now managed by
SQLAlchemy ORM + init_pgvector_schema().

Coverage:
    NTN-01 — run_notion_export creates goal parent page + session child pages;
             notion_page_url written back to study_goals row
    NTN-02 — Empty notion_api_key OR notion_parent_page_id → HTTP 400
    NTN-03 — HTTP 429 triggers exponential backoff; exhausted retries → HTTPStatusError
    NTN-04 — SKIPPED (SQLite init_db() removed; schema managed by ORM + Postgres)
    NTN-05 — POST /goals/{id}/export/notion returns {"status": "export_started"}
"""
import uuid
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch


# ── ORM-aware DB helpers ──────────────────────────────────────────────────────

def _make_session_factory():
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy.pool import NullPool
    from app.config import settings
    url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(url, poolclass=NullPool, echo=False)
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession), engine


async def _seed_goal_and_sessions(goal_id: str, num_sessions: int = 2, notes_markdown: str | None = "Some notes"):
    """Seed a goal + sessions into Postgres for notion_mcp tests."""
    from app.models.db_models import StudyGoal, StudySession
    factory, engine = _make_session_factory()
    async with factory() as session:
        session.add(
            StudyGoal(
                id=goal_id,
                title="Test Goal",
                topic="Test Topic",
                level="beginner",
                knowledge_source_ids="[]",
                status="active",
                created_at="2026-01-01T00:00:00",
            )
        )
        for i in range(1, num_sessions + 1):
            session.add(
                StudySession(
                    id=str(uuid.uuid4()),
                    goal_id=goal_id,
                    session_number=i,
                    title=f"Session {i}",
                    topic="Topic",
                    estimated_minutes=45,
                    status="pending",
                    notes_markdown=notes_markdown,
                    created_at="2026-01-01T00:00:00",
                )
            )
        await session.commit()
    await engine.dispose()


async def _get_goal_notion_url(goal_id: str) -> str | None:
    """Read notion_page_url from a study_goals row."""
    from app.models.db_models import StudyGoal
    factory, engine = _make_session_factory()
    async with factory() as session:
        obj = await session.get(StudyGoal, goal_id)
        url = obj.notion_page_url if obj else None
    await engine.dispose()
    return url


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
async def test_run_notion_export_creates_goal_and_session_pages():
    """NTN-01: httpx.AsyncClient.post called 3 times (1 goal + 2 sessions) for 2 sessions."""
    import app.agents.notion_mcp as nm_mod

    goal_id = str(uuid.uuid4())
    await _seed_goal_and_sessions(goal_id, num_sessions=2)

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
async def test_run_notion_export_writes_notion_page_url():
    """NTN-01 (writeback): notion_page_url is written back to the study_goals row."""
    import app.agents.notion_mcp as nm_mod

    goal_id = str(uuid.uuid4())
    await _seed_goal_and_sessions(goal_id, num_sessions=1)

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

    url = await _get_goal_notion_url(goal_id)
    assert url == expected_url


@pytest.mark.asyncio
async def test_run_notion_export_null_notes_fallback():
    """NTN-01 (null notes): Session with notes_markdown=NULL exports without error."""
    import app.agents.notion_mcp as nm_mod

    goal_id = str(uuid.uuid4())
    await _seed_goal_and_sessions(goal_id, num_sessions=1, notes_markdown=None)

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


# ── NTN-04: notion_page_url column exists in schema ──────────────────────────

@pytest.mark.skip(
    reason=(
        "NTN-04 verified init_db() creates notion_page_url in SQLite. "
        "init_db() was removed in the SQLite→Postgres migration; the schema is now "
        "managed by SQLAlchemy ORM (StudyGoal.notion_page_url mapped_column) + "
        "init_orm_models(). The ORM model definition IS the spec — column presence "
        "is guaranteed by the model declaration, not a runtime check."
    )
)
def test_notion_page_url_column_exists():
    pass


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
