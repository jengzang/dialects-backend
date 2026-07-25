from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.common.path import VOCABULARY_DB_PATH
from app.service.vocabulary.models import Base


def _sqlite_pragmas(dbapi_conn, _) -> None:
    cursor = dbapi_conn.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL;")
    except Exception as exc:
        print(f"[!] vocabulary.db 无法设置 WAL 模式: {exc}，使用默认 DELETE 模式")
        cursor.execute("PRAGMA journal_mode=DELETE;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()


def create_vocabulary_engine_and_session(db_path: str | Path = VOCABULARY_DB_PATH):
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
    event.listen(engine, "connect", _sqlite_pragmas)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine, session_factory


engine, SessionLocal = create_vocabulary_engine_and_session(VOCABULARY_DB_PATH)


_TABLE_COLUMNS_WITHOUT_USERNAME = {
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
        "created_at",
        "updated_at",
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
        "raw_location_json",
        "created_at",
        "updated_at",
    ],
    "vocabulary_permissions": [
        "id",
        "user_id",
        "permission_level",
        "created_at",
        "updated_at",
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


def _rebuild_table_without_username(conn, table_name: str) -> None:
    columns = _TABLE_COLUMNS_WITHOUT_USERNAME[table_name]
    quoted_columns = ", ".join(f'"{column}"' for column in columns)
    temp_table_name = f"{table_name}_new"

    conn.exec_driver_sql(f'DROP TABLE IF EXISTS "{temp_table_name}"')
    table = Base.metadata.tables[table_name]
    conn.exec_driver_sql(f'ALTER TABLE "{table_name}" RENAME TO "{temp_table_name}"')
    table.create(bind=conn, checkfirst=False)
    conn.exec_driver_sql(
        f'INSERT INTO "{table_name}" ({quoted_columns}) '
        f'SELECT {quoted_columns} FROM "{temp_table_name}"'
    )
    conn.exec_driver_sql(f'DROP TABLE "{temp_table_name}"')


def _drop_vocabulary_indexes(conn) -> None:
    rows = conn.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name IN "
        "('vocabulary_entries', 'vocabulary_locations', 'vocabulary_permissions') "
        "AND sql IS NOT NULL"
    ).fetchall()
    for row in rows:
        conn.exec_driver_sql(f'DROP INDEX IF EXISTS "{row[0]}"')


def migrate_remove_username_columns(target_engine: Engine) -> None:
    with target_engine.begin() as conn:
        tables_to_rebuild = [
            table_name
            for table_name in _TABLE_COLUMNS_WITHOUT_USERNAME
            if _table_exists(conn, table_name) and _table_has_column(conn, table_name, "username")
        ]
        if not tables_to_rebuild:
            return

        _drop_vocabulary_indexes(conn)
        for table_name in tables_to_rebuild:
            _rebuild_table_without_username(conn, table_name)


def migrate_vocabulary_database(target_engine: Engine = engine) -> None:
    Base.metadata.create_all(bind=target_engine)
    migrate_remove_username_columns(target_engine)
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
