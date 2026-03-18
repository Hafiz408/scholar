from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.database import get_engine
from app.db.database import init_db, init_pgvector_schema


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_pgvector_schema()
    yield


app = FastAPI(title="Scholar API", version="0.1.0", lifespan=lifespan)


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
