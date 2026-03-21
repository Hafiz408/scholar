import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.config import settings
from app.database import get_engine
from app.db.database import init_db, init_pgvector_schema
from app.routers.knowledge import router as knowledge_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # LangSmith tracing — inject into os.environ so LangChain runtime picks them up.
    # Only activate when LANGCHAIN_API_KEY is set; otherwise tracing is silently skipped.
    if settings.langsmith_api_key:
        os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
    init_db()
    init_pgvector_schema()
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
    from app.agents.orchestrator import build_graph
    async with AsyncSqliteSaver.from_conn_string(settings.sqlite_path) as checkpointer:
        app.state.checkpointer = checkpointer
        app.state.graph = build_graph(checkpointer)
        yield


app = FastAPI(title="Scholar API", version="0.1.0", lifespan=lifespan)
app.include_router(knowledge_router, prefix="/knowledge", tags=["knowledge"])

from app.routers.goals import router as goals_router
from app.routers.sessions import router as sessions_router
from app.routers.chat import router as chat_router
from app.routers.quiz import router as quiz_router
from app.routers.test import router as test_router

app.include_router(goals_router)
app.include_router(sessions_router)
app.include_router(chat_router)
app.include_router(quiz_router)
app.include_router(test_router)


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
