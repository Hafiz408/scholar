"""Async Postgres access shim mirroring the previous aiosqlite usage.

    async with pg.connect() as db:
        async with db.execute("SELECT ... WHERE id = %s", (x,)) as cur:
            row = await cur.fetchone()        # dict | None (dict_row)
        await db.execute("INSERT ... VALUES (%s)", (x,))
        await db.commit()

Placeholders are %s (psycopg3). Rows are dicts (psycopg dict_row).
"""
from contextlib import asynccontextmanager

import psycopg
from psycopg.rows import dict_row

from app.config import settings


class _CursorCM:
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
    raw = await psycopg.AsyncConnection.connect(settings.database_url, row_factory=dict_row)
    try:
        yield _ConnWrapper(raw)
    finally:
        await raw.close()
