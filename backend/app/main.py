import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.core.logging import (
    configure_logging,
    get_logger,
    get_request_id,
    new_request_id,
    set_request_id,
)
from app.core.database import get_async_engine, get_engine
from app.core.db_schema import init_orm_models, init_pgvector_schema
from app.routers.knowledge import router as knowledge_router
from app.routers.goals import router as goals_router
from app.routers.sessions import router as sessions_router
from app.routers.chat import router as chat_router
from app.routers.quiz import router as quiz_router
from app.routers.test import router as test_router
from app.routers.super import router as super_router

# Configure the root logger once, at import time, so every per-module logger inherits
# the centralized format and level (LOG_LEVEL, default INFO).
configure_logging()
logger = get_logger("scholar.requests")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # LangSmith tracing — inject into os.environ so LangChain runtime picks them up.
    # Only activate when LANGCHAIN_API_KEY is set; otherwise tracing is silently skipped.
    if settings.langsmith_api_key:
        os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
    # pgvector table + ivfflat index (+ dimension-change handling), then the ORM
    # metadata creates the relational tables (create_all is idempotent).
    init_pgvector_schema()
    await init_orm_models()
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from app.agents.orchestrator import build_graph
    async with AsyncPostgresSaver.from_conn_string(settings.database_url) as checkpointer:
        await checkpointer.setup()
        app.state.checkpointer = checkpointer
        app.state.graph = build_graph(checkpointer)
        try:
            yield
        finally:
            await get_async_engine().dispose()


app = FastAPI(title="Scholar API", version="0.1.0", lifespan=lifespan)

# Allow the Next.js frontend (any localhost port) to call the API directly.
# Needed because the frontend's /api proxy can pass through a trailing-slash
# redirect to an absolute backend URL, which the browser treats as cross-origin.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log two correlated lines per request (arrival + completion) sharing a request id."""
    rid = new_request_id()
    set_request_id(rid)

    method = request.method
    path = request.url.path
    query = request.url.query
    client = request.client.host if request.client else "-"

    # REQUEST line on arrival.
    arrival = f"→ [{rid}] {method} {path}"
    if query:
        arrival += f"?{query}"
    arrival += f" client={client}"
    logger.info(arrival)

    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        # Let the global handler format the response; just record the failure here.
        duration_ms = (time.perf_counter() - start) * 1000
        logger.exception(
            "✗ [%s] %s %s raised after %.2fms", rid, method, path, duration_ms
        )
        raise

    duration_ms = (time.perf_counter() - start) * 1000
    status_code = response.status_code
    if status_code >= 500:
        log = logger.error
    elif status_code >= 400:
        log = logger.warning
    else:
        log = logger.info
    # RESPONSE line on completion.
    log("← [%s] %s %s %d (%.2fms)", rid, method, path, status_code, duration_ms)

    response.headers["X-Request-ID"] = rid
    return response


def _error_headers(extra: dict | None = None) -> dict | None:
    """Merge the current request id (if any) into outgoing error response headers."""
    headers = dict(extra) if extra else {}
    rid = get_request_id()
    if rid:
        headers["X-Request-ID"] = rid
    return headers or None


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Consistent error shape for HTTPExceptions while preserving status/detail."""
    logger.warning(
        "[%s] HTTPException on %s -> %d: %s",
        get_request_id(),
        request.url.path,
        exc.status_code,
        exc.detail,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"status": exc.status_code, "detail": exc.detail}},
        headers=_error_headers(getattr(exc, "headers", None)),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Keep 422 with the standard field-level detail, in the consistent shape."""
    logger.warning(
        "[%s] Validation error on %s: %s",
        get_request_id(),
        request.url.path,
        exc.errors(),
    )
    return JSONResponse(
        status_code=422,
        content={"error": {"status": 422, "detail": exc.errors()}},
        headers=_error_headers(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all: log full traceback, never leak internals to the client."""
    logger.exception("[%s] Unhandled error on %s", get_request_id(), request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": {"status": 500, "detail": "Internal server error"}},
        headers=_error_headers(),
    )


app.include_router(knowledge_router, prefix="/knowledge", tags=["knowledge"])
app.include_router(goals_router)
app.include_router(sessions_router)
app.include_router(chat_router)
app.include_router(quiz_router)
app.include_router(test_router)
app.include_router(super_router)


@app.get("/health")
def health_check():
    try:
        engine = get_engine()
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            ).fetchone()
        pgvector_status = "active" if row else "missing"
    except Exception as e:
        return {"status": "error", "detail": str(e)}
    return {"status": "ok", "pgvector": pgvector_status}
