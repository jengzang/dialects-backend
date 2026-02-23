"""
数据库连接依赖
Database connection dependencies for FastAPI
"""
import sqlite3
from contextlib import contextmanager
from typing import Generator
from .config import DB_PATH, QUERY_TIMEOUT


@contextmanager
def get_db_connection():
    """
    数据库连接上下文管理器
    Database connection context manager

    Yields:
        sqlite3.Connection: Database connection with row_factory set to Row
    """
    conn = sqlite3.connect(
        DB_PATH,
        timeout=QUERY_TIMEOUT,
        check_same_thread=False  # 允许跨线程使用（FastAPI async 需要）
    )
    conn.row_factory = sqlite3.Row  # 返回字典格式
    try:
        yield conn
    finally:
        conn.close()


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
