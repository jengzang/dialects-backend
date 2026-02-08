"""
Database session management for Praat service.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import os
from pathlib import Path

from .models import Base

# Database path
DB_DIR = Path(__file__).parent.parent.parent / "data"
DB_DIR.mkdir(exist_ok=True)
DB_PATH = DB_DIR / "praat.db"

# Create engine with WAL mode for better concurrency
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False,
        "timeout": 30
    },
    poolclass=StaticPool,
    echo=False
)

# Create tables
Base.metadata.create_all(bind=engine)

# Enable WAL mode
with engine.connect() as conn:
    from sqlalchemy import text
    conn.execute(text("PRAGMA journal_mode=WAL"))
    conn.commit()

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_praat_db() -> Session:
    """Dependency for getting database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
