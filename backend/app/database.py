from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import get_settings

def get_engine():
    settings = get_settings()
    return create_engine(settings.database_url)

SessionLocal = sessionmaker(autocommit=False, autoflush=False)
Base = declarative_base()
