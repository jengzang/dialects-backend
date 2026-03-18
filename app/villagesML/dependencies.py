"""
数据库连接依赖
Database connection dependencies for FastAPI
"""
import sqlite3
from contextlib import contextmanager
from typing import Generator
from .config import DB_PATH, QUERY_TIMEOUT
from app.sql.db_pool import get_db_pool


# 获取 villagesML 数据库的连接池
_villages_pool = None

def get_villages_pool():
    """获取 villagesML 数据库连接池（单例模式）"""
    global _villages_pool
    if _villages_pool is None:
        _villages_pool = get_db_pool(DB_PATH)
    return _villages_pool


@contextmanager
def get_db_connection():
    """
    数据库连接上下文管理器（使用连接池）
    Database connection context manager using connection pool

    Yields:
        sqlite3.Connection: Database connection with row_factory set to Row
    """
    pool = get_villages_pool()
    with pool.get_connection() as conn:
        yield conn


def get_db() -> Generator[sqlite3.Connection, None, None]:
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
    with get_db_connection() as conn:
        yield conn


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
