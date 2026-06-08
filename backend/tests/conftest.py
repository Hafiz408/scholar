import asyncio
import pytest
import app.core.database as db


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: marks tests as integration tests (require live APIs)")


@pytest.fixture(autouse=True)
def _reset_async_engine():
    """Dispose + clear the cached async engine/sessionmaker before each test.

    The async engine is bound to the event loop it was created on.  Each
    ``asyncio.run(...)`` call creates a NEW event loop, so a cached engine from
    a previous call will fail with "got Future attached to a different loop".
    Resetting the globals here forces ``get_async_engine()`` to create a fresh
    engine bound to whatever loop the current test is using.
    """
    # Tear down any engine left over from a previous test.
    old_engine = db._async_engine
    db._async_engine = None
    db._async_sessionmaker = None

    if old_engine is not None:
        try:
            asyncio.run(old_engine.dispose())
        except Exception:
            pass

    yield

    # Tear down whatever the test created.
    eng = db._async_engine
    db._async_engine = None
    db._async_sessionmaker = None
    if eng is not None:
        try:
            asyncio.run(eng.dispose())
        except Exception:
            pass
