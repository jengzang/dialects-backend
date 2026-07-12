"""
数据库连接依赖
Database connection dependencies for FastAPI
"""
import sqlite3
from contextlib import contextmanager
from typing import Generator
from fastapi import HTTPException, Query

from .schema_config import DEFAULT_DATABASE_KEY
from .schema_runtime import install_schema_views, resolve_db_path
from app.sql.db_pool import get_db_pool


# 获取 villagesML 数据库的连接池
_villages_pools = {}

def get_villages_pool(dbpath: str = DEFAULT_DATABASE_KEY):
    """获取 villagesML 数据库连接池（单例模式）"""
    db_file = resolve_db_path(dbpath)
    if db_file not in _villages_pools:
        _villages_pools[db_file] = get_db_pool(db_file)
    return _villages_pools[db_file]


@contextmanager
def get_db_connection(dbpath: str = DEFAULT_DATABASE_KEY):
    """
    数据库连接上下文管理器（使用连接池）
    Database connection context manager using connection pool

    Yields:
        sqlite3.Connection: Database connection with row_factory set to Row
    """
    pool = get_villages_pool(dbpath)
    with pool.get_connection() as conn:
        install_schema_views(conn, dbpath)
        yield conn


def get_db(
    dbpath: str = Query(
        DEFAULT_DATABASE_KEY,
        description="VillagesML database mapping key, not a filesystem path",
    )
) -> Generator[sqlite3.Connection, None, None]:
    """
    FastAPI依赖注入函数
    FastAPI dependency injection function

    Usage:
        @app.get("/endpoint")
        def endpoint(db: sqlite3.Connection = Depends(get_db)):
            cursor = db.cursor()
            ...

    Yields:
        sqlite3.Connection: Database connection
    """
    try:
        resolve_db_path(dbpath)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    with get_db_connection(dbpath) as conn:
        yield conn


def get_dbpath(
    dbpath: str = Query(
        DEFAULT_DATABASE_KEY,
        description="VillagesML database mapping key, not a filesystem path",
    )
) -> str:
    """Return the selected VillagesML database mapping key for sibling dependencies."""
    try:
        resolve_db_path(dbpath)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return dbpath


def execute_query(conn: sqlite3.Connection, query: str, params: tuple = ()) -> list:
    """
    执行查询并返回结果列表
    Execute query and return results as list of dicts

    Args:
        conn: Database connection
        query: SQL query string
        params: Query parameters tuple

    Returns:
        list: List of row dictionaries
    """
    cursor = conn.cursor()
    cursor.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]


def execute_single(conn: sqlite3.Connection, query: str, params: tuple = ()) -> dict | None:
    """
    执行查询并返回单条结果
    Execute query and return single result

    Args:
        conn: Database connection
        query: SQL query string
        params: Query parameters tuple

    Returns:
        dict | None: Single row dictionary or None
    """
    cursor = conn.cursor()
    cursor.execute(query, params)
    row = cursor.fetchone()
    return dict(row) if row else None
