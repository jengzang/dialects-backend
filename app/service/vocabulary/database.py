from pathlib import Path
import sqlite3

from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.common.path import VOCABULARY_DB_PATH
from app.service.vocabulary.models import Base

VOCABULARY_SQLITE_BUSY_TIMEOUT_MS = 10000


def _sqlite_pragmas(dbapi_conn, _) -> None:
    cursor = dbapi_conn.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL;")
    except Exception as exc:
        print(f"[!] vocabulary.db 无法设置 WAL 模式: {exc}，使用默认 DELETE 模式")
        cursor.execute("PRAGMA journal_mode=DELETE;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.execute(f"PRAGMA busy_timeout={VOCABULARY_SQLITE_BUSY_TIMEOUT_MS};")
    cursor.close()


def create_vocabulary_engine_and_session(db_path: str | Path = VOCABULARY_DB_PATH):
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={
            "check_same_thread": False,
            "timeout": VOCABULARY_SQLITE_BUSY_TIMEOUT_MS / 1000,
        },
        pool_pre_ping=True,
    )
    event.listen(engine, "connect", _sqlite_pragmas)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine, session_factory


engine, SessionLocal = create_vocabulary_engine_and_session(VOCABULARY_DB_PATH)

try:
    Base.metadata.create_all(bind=engine)
except Exception as exc:
    if "already exists" not in str(exc).lower():
        raise


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def is_vocabulary_database_locked(exc: BaseException) -> bool:
    message = str(exc).lower()
    if "database is locked" not in message and "database table is locked" not in message:
        return False
    if isinstance(exc, sqlite3.OperationalError):
        return True
    return exc.__class__.__name__ == "OperationalError"


def vocabulary_database_busy_exception() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail="词表数据库正在写入，请稍后重试",
    )


def raise_vocabulary_database_busy_if_locked(exc: BaseException) -> None:
    if is_vocabulary_database_locked(exc):
        raise vocabulary_database_busy_exception() from exc
