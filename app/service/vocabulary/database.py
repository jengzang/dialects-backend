from pathlib import Path
import sqlite3

from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.common.path import VOCABULARY_DB_PATH
from app.service.vocabulary.models import TONE_COLUMNS, Base

VOCABULARY_SQLITE_BUSY_TIMEOUT_MS = 10000
LOCATION_METADATA_COLUMNS = {
    "vocabulary_source": "TEXT DEFAULT ''",
    "description": "TEXT DEFAULT ''",
    "other": "TEXT DEFAULT ''",
}


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


def _ensure_location_columns(
    target_engine: Engine,
    columns: dict[str, str],
    *,
    label: str,
) -> None:
    try:
        with target_engine.connect() as conn:
            existing = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(vocabulary_locations)")}
            missing = [column for column in columns if column not in existing]
        for column in missing:
            try:
                with target_engine.begin() as conn:
                    conn.exec_driver_sql(
                        f"ALTER TABLE vocabulary_locations ADD COLUMN {column} {columns[column]}"
                    )
            except Exception as exc:
                if "duplicate column name" not in str(exc).lower():
                    raise
        if missing:
            print(f"[vocabulary] 已补充{label}: {', '.join(missing)}")
    except Exception as exc:
        print(f"[!] vocabulary_locations {label}迁移失败: {exc}")


def _ensure_tone_columns(target_engine: Engine = engine) -> None:
    """create_all 不会给已存在的表补列，这里手动补齐調值列（T1-T10）。"""
    _ensure_location_columns(
        target_engine,
        {column: "VARCHAR(50) DEFAULT ''" for column in TONE_COLUMNS},
        label="調值列",
    )


def _ensure_location_metadata_columns(target_engine: Engine = engine) -> None:
    """create_all 不会给已存在的表补列，这里手动补齐地点元数据列。"""
    _ensure_location_columns(
        target_engine,
        LOCATION_METADATA_COLUMNS,
        label="地点元数据列",
    )


def _ensure_entry_indexes() -> None:
    """create_all 不会给已存在的表补索引，这里手动补齐复合索引。

    该复合索引让 standard-words 的分组聚合走覆盖索引有序扫描，避免 temp b-tree 排序。
    """
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS idx_vocabulary_entries_standard_word_location "
                "ON vocabulary_entries(standard_word, location_name)"
            )
    except Exception as exc:
        print(f"[!] vocabulary_entries 复合索引迁移失败: {exc}")


_ensure_tone_columns()
_ensure_location_metadata_columns()
_ensure_entry_indexes()


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
