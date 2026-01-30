import os
import sqlite3

from fastapi import HTTPException

from common.config import YC_SPOKEN_DB_PATH, GD_VILLAGE_DB_PATH, CHARACTERS_DB_PATH

DB_MAPPING = {
    "spoken": YC_SPOKEN_DB_PATH,
    "village": GD_VILLAGE_DB_PATH,
    "chars": CHARACTERS_DB_PATH,
}
def get_db_connection(db_key: str):
    """根据代号获取对应的数据库连接"""
    db_path = DB_MAPPING.get(db_key)

    if not db_path:
        raise HTTPException(status_code=400, detail=f"无效的数据库代号: {db_key}")

    if not os.path.exists(db_path):
        raise HTTPException(status_code=500, detail=f"数据库文件不存在: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn