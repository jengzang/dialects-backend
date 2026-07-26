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


_EXPECTED_TABLE_COLUMNS = {
    "vocabulary_entries": [
        "id",
        "user_id",
        "location_name",
        "standard_word",
        "local_expression",
        "ipa",
        "notes",
        "informations",
        "source_filename",
    ],
    "vocabulary_locations": [
        "id",
        "user_id",
        "location_name",
        "coordinates",
        "province",
        "city",
        "county",
        "town",
        "administrative_village",
        "natural_village",
        "yindian_region",
        "atlas_region",
    ],
    "vocabulary_permissions": [
        "id",
        "user_id",
        "permission_level",
    ],
    "vocabulary_logs": [
        "id",
        "operation_id",
        "user_id",
        "permission_level",
        "source",
        "action",
        "table_name",
        "target_scope",
        "affected_rows",
        "status",
        "payload_json",
        "created_at",
    ],
}


def _table_exists(conn, table_name: str) -> bool:
    result = conn.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    return result.fetchone() is not None


def _table_has_column(conn, table_name: str, column_name: str) -> bool:
    rows = conn.exec_driver_sql(f'PRAGMA table_info("{table_name}")').fetchall()
    return any(row[1] == column_name for row in rows)


def _get_existing_columns(conn, table_name: str) -> list[str]:
    rows = conn.exec_driver_sql(f'PRAGMA table_info("{table_name}")').fetchall()
    return [row[1] for row in rows]


def _get_column_metadata(conn, table_name: str) -> dict[str, dict[str, object]]:
    rows = conn.exec_driver_sql(f'PRAGMA table_info("{table_name}")').fetchall()
    return {
        row[1]: {
            "type": row[2],
            "notnull": bool(row[3]),
            "default_value": row[4],
            "pk": bool(row[5]),
        }
        for row in rows
    }


def _rebuild_table_with_expected_columns(conn, table_name: str) -> None:
    columns = _EXPECTED_TABLE_COLUMNS[table_name]
    existing_columns = set(_get_existing_columns(conn, table_name))
    preserved_columns = [column for column in columns if column in existing_columns]
    quoted_columns = ", ".join(f'"{column}"' for column in preserved_columns)
    temp_table_name = f"{table_name}_new"

    conn.exec_driver_sql(f'DROP TABLE IF EXISTS "{temp_table_name}"')
    table = Base.metadata.tables[table_name]
    conn.exec_driver_sql(f'ALTER TABLE "{table_name}" RENAME TO "{temp_table_name}"')
    table.create(bind=conn, checkfirst=False)
    if preserved_columns:
        conn.exec_driver_sql(
            f'INSERT INTO "{table_name}" ({quoted_columns}) '
            f'SELECT {quoted_columns} FROM "{temp_table_name}"'
        )
    conn.exec_driver_sql(f'DROP TABLE "{temp_table_name}"')


def _drop_vocabulary_indexes(conn) -> None:
    rows = conn.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name IN "
        "('vocabulary_entries', 'vocabulary_locations', 'vocabulary_permissions', 'vocabulary_logs') "
        "AND sql IS NOT NULL"
    ).fetchall()
    for row in rows:
        conn.exec_driver_sql(f'DROP INDEX IF EXISTS "{row[0]}"')


def migrate_remove_username_columns(target_engine: Engine) -> None:
    with target_engine.begin() as conn:
        tables_to_rebuild = [
            table_name
            for table_name in _EXPECTED_TABLE_COLUMNS
            if _table_exists(conn, table_name) and _table_has_column(conn, table_name, "username")
        ]
        if not tables_to_rebuild:
            return

        _drop_vocabulary_indexes(conn)
        for table_name in tables_to_rebuild:
            _rebuild_table_with_expected_columns(conn, table_name)


def migrate_remove_unused_timestamp_columns(target_engine: Engine) -> None:
    with target_engine.begin() as conn:
        tables_to_rebuild = [
            table_name
            for table_name in (
                "vocabulary_entries",
                "vocabulary_locations",
                "vocabulary_permissions",
            )
            if _table_exists(conn, table_name)
            and (
                _table_has_column(conn, table_name, "created_at")
                or _table_has_column(conn, table_name, "updated_at")
            )
        ]
        if not tables_to_rebuild:
            return

        _drop_vocabulary_indexes(conn)
        for table_name in tables_to_rebuild:
            _rebuild_table_with_expected_columns(conn, table_name)


def migrate_remove_legacy_location_raw_json_column(target_engine: Engine) -> None:
    with target_engine.begin() as conn:
        if not _table_exists(conn, "vocabulary_locations"):
            return
        if not _table_has_column(conn, "vocabulary_locations", "raw_location_json"):
            return

        _drop_vocabulary_indexes(conn)
        _rebuild_table_with_expected_columns(conn, "vocabulary_locations")


def migrate_vocabulary_logs_operation_columns(target_engine: Engine) -> None:
    with target_engine.begin() as conn:
        if not _table_exists(conn, "vocabulary_logs"):
            return

        existing_columns = set(_get_existing_columns(conn, "vocabulary_logs"))
        if "operation_id" not in existing_columns:
            conn.exec_driver_sql(
                'ALTER TABLE "vocabulary_logs" ADD COLUMN "operation_id" VARCHAR(36) DEFAULT ""'
            )
        if "source" not in existing_columns:
            conn.exec_driver_sql(
                'ALTER TABLE "vocabulary_logs" ADD COLUMN "source" VARCHAR(50) DEFAULT "legacy"'
            )
        if "status" not in existing_columns:
            conn.exec_driver_sql(
                'ALTER TABLE "vocabulary_logs" ADD COLUMN "status" VARCHAR(20) DEFAULT "success"'
            )

        conn.exec_driver_sql(
            "UPDATE vocabulary_logs "
            "SET operation_id = 'legacy-' || id "
            "WHERE operation_id IS NULL OR operation_id = ''"
        )
        conn.exec_driver_sql(
            "UPDATE vocabulary_logs SET source = 'legacy' "
            "WHERE source IS NULL OR source = ''"
        )
        conn.exec_driver_sql(
            "UPDATE vocabulary_logs SET status = 'success' "
            "WHERE status IS NULL OR status = ''"
        )

        column_metadata = _get_column_metadata(conn, "vocabulary_logs")
        required_columns = ("operation_id", "source", "status")
        if any(not column_metadata[column]["notnull"] for column in required_columns):
            _drop_vocabulary_indexes(conn)
            _rebuild_table_with_expected_columns(conn, "vocabulary_logs")


def migrate_vocabulary_database(target_engine: Engine = engine) -> None:
    Base.metadata.create_all(bind=target_engine)
    migrate_remove_username_columns(target_engine)
    migrate_remove_unused_timestamp_columns(target_engine)
    migrate_remove_legacy_location_raw_json_column(target_engine)
    migrate_vocabulary_logs_operation_columns(target_engine)
    Base.metadata.create_all(bind=target_engine)



try:
    migrate_vocabulary_database()
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
