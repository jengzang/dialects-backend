"""一次性脚本：重建 vocabulary.db，确保物理表约束和模型定义一致。

用法: PYTHONPATH=. python scripts/vocabulary/rebuild_db.py [db_path]
"""

import sys

from app.service.vocabulary.database import create_vocabulary_engine_and_session
from app.service.vocabulary.models import Base


def rebuild(db_path: str) -> None:
    engine, _ = create_vocabulary_engine_and_session(db_path)

    tables = [
        "vocabulary_entries",
        "vocabulary_locations",
        "vocabulary_permissions",
        "vocabulary_logs",
    ]

    # 1. 读取全部数据（用 mappings 获取 dict，key 为列名）
    saved: dict[str, list[dict]] = {}
    with engine.connect() as conn:
        for table_name in tables:
            result = conn.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            )
            if result.fetchone() is None:
                saved[table_name] = []
                print(f"  {table_name}: 表不存在，跳过")
                continue
            rows = conn.exec_driver_sql(f"SELECT * FROM {table_name}").mappings().all()
            saved[table_name] = [dict(r) for r in rows]
            print(f"  读取 {table_name}: {len(rows)} 行")

    # 2. 删表
    with engine.begin() as conn:
        for table_name in tables:
            conn.exec_driver_sql(f"DROP TABLE IF EXISTS {table_name}")
    print("  已删除所有表")

    # 3. 从模型重建
    Base.metadata.create_all(bind=engine)
    print("  已通过模型重建所有表")

    # 4. 恢复数据（只写新表中存在的列）
    with engine.begin() as conn:
        for table_name, rows in saved.items():
            if not rows:
                continue
            new_cols = [
                row[1]
                for row in conn.exec_driver_sql(
                    f'PRAGMA table_info("{table_name}")'
                ).fetchall()
            ]
            quoted = ", ".join(f'"{c}"' for c in new_cols)
            placeholders = ", ".join(["?"] * len(new_cols))
            inserted = 0
            for row_dict in rows:
                values = tuple(row_dict.get(c) for c in new_cols)
                conn.exec_driver_sql(
                    f'INSERT INTO "{table_name}" ({quoted}) VALUES ({placeholders})',
                    values,
                )
                inserted += 1
            print(f"  恢复 {table_name}: {inserted} 行")

    print(f"\n重建完成: {db_path}")


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "data/vocabulary.db"
    rebuild(db_path)
