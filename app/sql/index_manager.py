"""
Database Index Manager
自动检查并创建数据库索引以优化查询性能
"""

import sqlite3
from typing import List, Set
from common.config import (
    DIALECTS_DB_USER,
    DIALECTS_DB_ADMIN,
    CHARACTERS_DB_PATH,
    QUERY_DB_USER
)


def ensure_indexes(db_path: str) -> None:
    """
    确保数据库中存在所有必要的索引

    Args:
        db_path: 数据库文件路径
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 获取现有索引
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        existing_indexes: Set[str] = {row[0] for row in cursor.fetchall()}

        # 定义需要创建的索引
        indexes = [
            # 优先级1: 字符+地点复合索引（针对search_chars.py的核心查询）
            "CREATE INDEX IF NOT EXISTS idx_dialects_char_abbr ON dialects(漢字, 簡稱)",
            "CREATE INDEX IF NOT EXISTS idx_dialects_char_abbr2 ON dialects(簡稱, 漢字)",

            # 优先级2: 地点查询索引
            "CREATE INDEX IF NOT EXISTS idx_dialects_abbr ON dialects(簡稱)",

            # 优先级3: 特征列索引（用于phonology2status.py的GROUP BY查询）
            "CREATE INDEX IF NOT EXISTS idx_dialects_features1 ON dialects(簡稱, 聲母)",
            "CREATE INDEX IF NOT EXISTS idx_dialects_features2 ON dialects(簡稱, 韻母)",
            "CREATE INDEX IF NOT EXISTS idx_dialects_features3 ON dialects(簡稱, 聲調)",

            # 优先级4: 多音字查询索引（优化完整的多音字查询路径）
            "CREATE INDEX IF NOT EXISTS idx_dialects_polyphonic ON dialects(多音字, 漢字)",
            "CREATE INDEX IF NOT EXISTS idx_dialects_poly_full ON dialects(多音字, 簡稱, 漢字)",

            # 优先级5: 存储标记索引（用于match_input_tip.py的有效地点过滤）
            "CREATE INDEX IF NOT EXISTS idx_dialects_storage ON dialects(存儲標記, 簡稱)",

            # 单字符索引（用于简单的字符查询）
            "CREATE INDEX IF NOT EXISTS idx_dialects_char ON dialects(漢字)",

            # 音节索引（用于音节查询）
            "CREATE INDEX IF NOT EXISTS idx_dialects_syllable ON dialects(音節)",
        ]

        # 创建索引
        created_count = 0
        for idx_sql in indexes:
            # 提取索引名称
            idx_name = idx_sql.split("IF NOT EXISTS")[1].split("ON")[0].strip()

            if idx_name not in existing_indexes:
                cursor.execute(idx_sql)
                created_count += 1
                print(f"  ✓ 创建索引: {idx_name}")

        # 优化查询计划器统计信息
        cursor.execute("ANALYZE")

        conn.commit()
        conn.close()

        if created_count > 0:
            print(f"  → 在 {db_path} 中创建了 {created_count} 个索引")
        else:
            print(f"  → {db_path} 所有索引已存在")

    except Exception as e:
        print(f"  ✗ 创建索引失败 ({db_path}): {e}")


def ensure_character_indexes(db_path: str) -> None:
    """
    确保characters数据库中存在必要的索引

    Args:
        db_path: 数据库文件路径
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        indexes = [
            # 字符查询索引（最常用）
            "CREATE INDEX IF NOT EXISTS idx_characters_char ON characters(漢字)",

            # 多地位标记索引
            "CREATE INDEX IF NOT EXISTS idx_characters_multi ON characters(多地位標記, 漢字)",

            # 音韵层级索引（用于status_arrange_pho.py的分组统计）
            "CREATE INDEX IF NOT EXISTS idx_characters_hierarchy ON characters(組, 母, 攝, 韻, 調)",

            # 等级查询索引（用于等=三的特殊处理）
            "CREATE INDEX IF NOT EXISTS idx_characters_grade ON characters(等, 漢字)",
        ]

        created_count = 0
        for idx_sql in indexes:
            idx_name = idx_sql.split("IF NOT EXISTS")[1].split("ON")[0].strip()
            cursor.execute(idx_sql)
            created_count += 1

        cursor.execute("ANALYZE")
        conn.commit()
        conn.close()

        print(f"  → 在 characters.db 中确保了 {created_count} 个索引")

    except Exception as e:
        print(f"  ✗ 创建索引失败 (characters.db): {e}")


def ensure_query_indexes(db_path: str) -> None:
    """
    确保query_dialects数据库中存在必要的索引

    Args:
        db_path: 数据库文件路径
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        indexes = [
            # 地点+存储标记复合索引（用于match_input_tip.py）
            "CREATE INDEX IF NOT EXISTS idx_query_abbr_storage ON dialects(簡稱, 存儲標記)",

            # 音典分区+存储标记索引（用于getloc_by_name_region.py的模糊查询）
            "CREATE INDEX IF NOT EXISTS idx_query_partition_storage ON dialects(音典分區, 存儲標記)",

            # 地图集分区+存储标记索引
            "CREATE INDEX IF NOT EXISTS idx_query_atlas_storage ON dialects(地圖集二分區, 存儲標記)",

            # 地理位置索引（用于地理名称匹配）
            "CREATE INDEX IF NOT EXISTS idx_query_geo_town ON dialects(鎮)",
            "CREATE INDEX IF NOT EXISTS idx_query_geo_village ON dialects(行政村)",
            "CREATE INDEX IF NOT EXISTS idx_query_geo_nature ON dialects(自然村)",

            # 经纬度查询索引
            "CREATE INDEX IF NOT EXISTS idx_query_coordinates ON dialects(簡稱, 經緯度)",
        ]

        created_count = 0
        for idx_sql in indexes:
            idx_name = idx_sql.split("IF NOT EXISTS")[1].split("ON")[0].strip()
            cursor.execute(idx_sql)
            created_count += 1

        cursor.execute("ANALYZE")
        conn.commit()
        conn.close()

        print(f"  → 在 query_dialects.db 中确保了 {created_count} 个索引")

    except Exception as e:
        print(f"  ✗ 创建索引失败 (query_dialects.db): {e}")


def initialize_all_indexes() -> None:
    """
    初始化所有数据库的索引
    在应用启动时调用此函数
    """
    print("\n[FIX] 开始初始化数据库索引...")

    # 方言数据库索引
    print("\n[DB] 方言数据库 (dialects):")
    ensure_indexes(DIALECTS_DB_USER)
    ensure_indexes(DIALECTS_DB_ADMIN)

    # 字符数据库索引
    print("\n📚 字符数据库 (characters):")
    ensure_character_indexes(CHARACTERS_DB_PATH)

    # 查询数据库索引
    print("\n[SEARCH] 查询数据库 (query):")
    from common.config import QUERY_DB_ADMIN, QUERY_DB_USER
    if QUERY_DB_USER:
        ensure_query_indexes(QUERY_DB_USER)
    if QUERY_DB_ADMIN:
        ensure_query_indexes(QUERY_DB_ADMIN)

    print("\n[OK] 所有数据库索引初始化完成\n")


def drop_all_indexes(db_path: str) -> None:
    """
    删除所有创建的索引（仅用于回滚/调试）

    Args:
        db_path: 数据库文件路径
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        index_names = [
            # dialects 索引
            "idx_dialects_char_abbr",
            "idx_dialects_abbr",
            "idx_dialects_features",
            "idx_dialects_polyphonic",
            "idx_dialects_poly_full",
            "idx_dialects_storage",
            "idx_dialects_char",
            "idx_dialects_syllable",
            # characters 索引
            "idx_characters_char",
            "idx_characters_multi",
            "idx_characters_hierarchy",
            "idx_characters_grade",
            # query 索引
            "idx_query_abbr_storage",
            "idx_query_partition_storage",
            "idx_query_atlas_storage",
            "idx_query_geo_town",
            "idx_query_geo_village",
            "idx_query_geo_nature",
            "idx_query_coordinates",
        ]

        for idx_name in index_names:
            try:
                cursor.execute(f"DROP INDEX IF EXISTS {idx_name}")
                print(f"  ✓ 删除索引: {idx_name}")
            except Exception as e:
                print(f"  ✗ 删除索引失败 ({idx_name}): {e}")

        conn.commit()
        conn.close()
        print(f"  → 索引删除完成: {db_path}")

    except Exception as e:
        print(f"  ✗ 删除索引失败 ({db_path}): {e}")


if __name__ == "__main__":
    # 命令行工具：可以手动运行此脚本来创建索引
    import sys
    from common.config import QUERY_DB_ADMIN, QUERY_DB_USER

    if len(sys.argv) > 1 and sys.argv[1] == "drop":
        print("[DEL] 删除所有索引...")
        drop_all_indexes(DIALECTS_DB_USER)
        drop_all_indexes(DIALECTS_DB_ADMIN)
        drop_all_indexes(CHARACTERS_DB_PATH)
        if QUERY_DB_USER:
            drop_all_indexes(QUERY_DB_USER)
        if QUERY_DB_ADMIN:
            drop_all_indexes(QUERY_DB_ADMIN)
    else:
        initialize_all_indexes()
