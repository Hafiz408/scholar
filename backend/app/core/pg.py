"""Async Postgres access with a shared connection pool.

App request path (inside the app event loop):
    async with pg.connect() as db:
        async with db.execute("SELECT ... WHERE id = %s", (x,)) as cur:
            row = await cur.fetchone()        # dict | None (dict_row)
        await db.execute("INSERT ... VALUES (%s)", (x,))
        await db.commit()

Tests / scripts running OUTSIDE the app's event loop must use connect_direct()
(an AsyncConnectionPool is bound to the loop it was opened on, so a one-off
connection avoids cross-loop errors):
    async with pg.connect_direct() as db:
        ...

Placeholders are %s (psycopg3); rows come back as dicts (dict_row).
"""
from contextlib import asynccontextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.config import settings

# Shared, lazily-opened pool for the app request path. Bound to the event loop
# it is opened on (see open_pool, called from the FastAPI lifespan).
_pool: AsyncConnectionPool | None = None


async def open_pool() -> None:
    """Open the shared async connection pool. Call once on app startup (lifespan)."""
    global _pool
    if _pool is None:
        _pool = AsyncConnectionPool(
            conninfo=settings.database_url,
            min_size=2,
            max_size=10,
            open=False,  # open explicitly below (constructor-open is deprecated)
            kwargs={"row_factory": dict_row},
        )
        await _pool.open()


async def close_pool() -> None:
    """Close the shared pool. Call on app shutdown (lifespan)."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


class _CursorCM:
    """Awaitable async cursor context manager so call sites can use either
    `async with db.execute(...) as cur:` or `await db.execute(...)`."""

    def __init__(self, conn, sql, params):
        self._conn = conn
        self._sql = sql
        self._params = params
        self._cur = None

    async def _run(self):
        self._cur = self._conn.cursor()
        await self._cur.execute(self._sql, self._params)
        return self._cur

    def __await__(self):
        return self._run().__await__()

    async def __aenter__(self):
        return await self._run()

    async def __aexit__(self, *exc):
        if self._cur is not None:
            await self._cur.close()
        return False


class _ConnWrapper:
    def __init__(self, raw):
        self._raw = raw

    def execute(self, sql, params=()):
        return _CursorCM(self._raw, sql, params)

    async def commit(self):
        await self._raw.commit()


@asynccontextmanager
async def connect():
    """Lease a pooled connection (app request path). The pool's context manager
    commits on clean exit and rolls back on error, so explicit `await db.commit()`
    calls remain valid (and idempotent)."""
    if _pool is None:
        raise RuntimeError(
            "Postgres pool not initialized — open_pool() must run in the app lifespan. "
            "Use connect_direct() for tests/scripts outside the app event loop."
        )
    async with _pool.connection() as raw:
        yield _ConnWrapper(raw)


@asynccontextmanager
async def connect_direct():
    """One-off (non-pooled) connection for tests/scripts outside the app loop."""
    raw = await psycopg.AsyncConnection.connect(
        settings.database_url, row_factory=dict_row
    )
    try:
        yield _ConnWrapper(raw)
    finally:
        await raw.close()
