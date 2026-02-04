"""
数据库连接池管理器
使用 SQLite 连接池优化数据库访问性能
"""
import sqlite3
import threading
from queue import Queue, Empty
from contextlib import contextmanager
from typing import Optional
import time


class SQLiteConnectionPool:
    """SQLite 连接池"""

    def __init__(self, db_path: str, pool_size: int = 10, timeout: float = 30.0):
        """
        初始化连接池

        Args:
            db_path: 数据库文件路径
            pool_size: 连接池大小
            timeout: 获取连接的超时时间（秒）
        """
        self.db_path = db_path
        self.pool_size = pool_size
        self.timeout = timeout
        self._pool = Queue(maxsize=pool_size)
        self._lock = threading.Lock()
        self._created_count = 0

        # 预创建连接
        for _ in range(pool_size):
            self._pool.put(self._create_connection())
            self._created_count += 1

    def _create_connection(self) -> sqlite3.Connection:
        """创建新的数据库连接"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        # 优化 SQLite 性能
        conn.execute("PRAGMA journal_mode=WAL")  # 使用 WAL 模式提升并发性能
        conn.execute("PRAGMA synchronous=NORMAL")  # 平衡性能和安全
        conn.execute("PRAGMA cache_size=-16000")  # 16MB 缓存（优化内存使用）
        conn.execute("PRAGMA temp_store=MEMORY")  # 临时表存储在内存
        return conn

    @contextmanager
    def get_connection(self):
        """
        获取连接（上下文管理器）

        Usage:
            with pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM table")
        """
        conn = None
        try:
            # 尝试从池中获取连接
            try:
                conn = self._pool.get(timeout=self.timeout)
            except Empty:
                # 如果池中没有连接且未达到最大连接数，创建新连接
                with self._lock:
                    if self._created_count < self.pool_size * 2:  # 允许动态扩展到2倍
                        conn = self._create_connection()
                        self._created_count += 1
                    else:
                        raise TimeoutError(f"无法在 {self.timeout} 秒内获取数据库连接")

            yield conn

        finally:
            # 归还连接到池中
            if conn is not None:
                try:
                    # 检查连接是否仍然有效
                    conn.execute("SELECT 1")
                    self._pool.put(conn, block=False)
                except (sqlite3.Error, Exception):
                    # 连接已损坏，创建新连接补充到池中
                    try:
                        conn.close()
                    except:
                        pass
                    try:
                        new_conn = self._create_connection()
                        self._pool.put(new_conn, block=False)
                    except:
                        pass

    def close_all(self):
        """关闭所有连接"""
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                conn.close()
            except (Empty, Exception):
                break


class DatabasePoolManager:
    """数据库连接池管理器（单例模式）"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._pools = {}
        self._initialized = True

    def get_pool(self, db_path: str, pool_size: int = 10) -> SQLiteConnectionPool:
        """
        获取或创建指定数据库的连接池

        Args:
            db_path: 数据库文件路径
            pool_size: 连接池大小

        Returns:
            SQLiteConnectionPool 实例
        """
        if db_path not in self._pools:
            with self._lock:
                if db_path not in self._pools:
                    self._pools[db_path] = SQLiteConnectionPool(db_path, pool_size)
        return self._pools[db_path]

    def close_all(self):
        """关闭所有连接池"""
        for pool in self._pools.values():
            pool.close_all()
        self._pools.clear()


# 全局连接池管理器实例
db_pool_manager = DatabasePoolManager()


def get_db_pool(db_path: str, pool_size: int = 10) -> SQLiteConnectionPool:
    """
    获取数据库连接池的便捷函数

    Args:
        db_path: 数据库文件路径
        pool_size: 连接池大小

    Returns:
        SQLiteConnectionPool 实例
    """
    return db_pool_manager.get_pool(db_path, pool_size)


def close_all_pools():
    """关闭所有数据库连接池"""
    db_pool_manager.close_all()
