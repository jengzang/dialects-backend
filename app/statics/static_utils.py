# app/static_utils.py
"""
[PKG] 靜態資源工具模塊：處理 get_resource_path，用於靜態文件路徑兼容 PyInstaller。
"""

import os
import shutil
import sys


# ----------------------------------------
# 路径工具：兼容 PyInstaller 和普通运行
# ----------------------------------------

def get_resource_path(relative_path: str) -> str:
    """
    根據 PyInstaller 或普通執行，動態獲取資源目錄的絕對路徑。
    """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.abspath(relative_path)


# ----------------------------------------
# 要持久化的 DB 文件列表
# ----------------------------------------

PERSISTENT_DBS = [
    "supplements.db",
    "auth.db",
    # 如果需要更多用户可写数据库，只需加在这里
]


# ----------------------------------------
# 初始化 userdata 下的 DB 文件
# ----------------------------------------

def ensure_user_data() -> str:
    """
    確保 userdata 目錄下的指定 .db 文件存在，若被刪除將自動從內置資源還原。
    返回 userdata 的完整路徑（用於掛載）。
    """
    user_data_dir = os.path.abspath("userdata")
    os.makedirs(user_data_dir, exist_ok=True)

    for db_file in PERSISTENT_DBS:
        user_db_path = os.path.join(user_data_dir, db_file)
        if not os.path.exists(user_db_path):
            # 拷貝內建預設 DB 到 userdata
            default_path = get_resource_path(f"data/{db_file}")
            if os.path.exists(default_path):
                shutil.copy2(default_path, user_db_path)
            else:
                print(f"[警告] 預設檔案缺失：{default_path}")

    return user_data_dir
