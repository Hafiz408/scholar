from contextlib import asynccontextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import get_settings

# Cache a single pooled engine process-wide. Creating a new engine per call would
# spin up a fresh connection pool each time (a scalability leak); SQLAlchemy's
# QueuePool here is shared across requests with pre-ping + recycle for resilience.
_engine = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=1800,
        )
    return _engine

SessionLocal = sessionmaker(autocommit=False, autoflush=False)
Base = declarative_base()


# --- Async engine + session (SQLAlchemy 2.0 / asyncpg) ---------------------
# The async stack is the forward path for data-access code. It coexists with the
# sync engine above (still used by /health and legacy paths this phase) and with
# the raw app/core/pg.py psycopg shim. Like the sync engine, the async engine and
# its sessionmaker are cached process-wide to share a single connection pool.
_async_engine = None
_async_sessionmaker = None


def _to_async_url(url: str) -> str:
    """Map a psycopg-style URL to the asyncpg driver URL.

    postgresql://...  ->  postgresql+asyncpg://...
    """
    return url.replace("postgresql://", "postgresql+asyncpg://", 1)


def get_async_engine():
    global _async_engine
    if _async_engine is None:
        s = get_settings()
        _async_engine = create_async_engine(
            _to_async_url(s.database_url),
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=1800,
            echo=False,
        )
    return _async_engine


def get_sessionmaker():
    global _async_sessionmaker
    if _async_sessionmaker is None:
        _async_sessionmaker = async_sessionmaker(
            get_async_engine(), expire_on_commit=False, class_=AsyncSession
        )
    return _async_sessionmaker


@asynccontextmanager
async def get_session():
    """Async session context manager for data-access code.

    Usage (later phases):
        async with get_session() as session:
            ...
    """
    sm = get_sessionmaker()
    async with sm() as session:
        yield session
