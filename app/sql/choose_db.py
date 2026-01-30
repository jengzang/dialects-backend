import os
import sqlite3

from fastapi import HTTPException

from common.config import YC_SPOKEN_DB_PATH, GD_VILLAGE_DB_PATH, CHARACTERS_DB_PATH, QUERY_DB_USER, QUERY_DB_ADMIN
from app.sql.db_pool import get_db_pool

DB_MAPPING = {
    "spoken": YC_SPOKEN_DB_PATH,
    "village": GD_VILLAGE_DB_PATH,
    "chars": CHARACTERS_DB_PATH,
    "query": QUERY_DB_USER,
    "query_admin": QUERY_DB_ADMIN,
}
def get_db_connection(db_key: str):
    """根据代号获取对应的数据库连接（使用连接池）"""
    db_path = DB_MAPPING.get(db_key)

    if not db_path:
        raise HTTPException(status_code=400, detail=f"无效的数据库代号: {db_key}")

    if not os.path.exists(db_path):
        raise HTTPException(status_code=500, detail=f"数据库文件不存在: {db_path}")

    pool = get_db_pool(db_path)
    return pool.get_connection()