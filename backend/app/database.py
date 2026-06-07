from sqlalchemy import create_engine, text
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
