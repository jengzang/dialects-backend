import sqlite3

db_path = "C:/Users/joengzaang/myfiles/server/fastapi/data/villages.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=== 检查 spatial_clusters 表 ===")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='spatial_clusters'")
table_exists = cursor.fetchone()

if table_exists:
    print("OK: spatial_clusters table exists")

    # 检查表结构
    print("\n=== 表结构 ===")
    cursor.execute("PRAGMA table_info(spatial_clusters)")
    for row in cursor.fetchall():
        print(f"{row[1]:20} {row[2]:15}")

    # 检查数据
    print("\n=== 数据统计 ===")
    cursor.execute("SELECT COUNT(*) FROM spatial_clusters")
    total = cursor.fetchone()[0]
    print(f"总记录数: {total:,}")

    if total > 0:
        # 检查 run_id
        print("\n=== 可用的 run_id ===")
        cursor.execute("SELECT DISTINCT run_id FROM spatial_clusters")
        for row in cursor.fetchall():
            print(f"  - {row[0]}")

        # 检查最新的 run_id
        cursor.execute("SELECT run_id, COUNT(*) as cnt FROM spatial_clusters GROUP BY run_id ORDER BY cnt DESC")
        print("\n=== run_id 统计 ===")
        for row in cursor.fetchall():
            print(f"  {row[0]}: {row[1]:,} 条记录")

        # 示例数据
        print("\n=== 示例数据 ===")
        cursor.execute("SELECT * FROM spatial_clusters LIMIT 3")
        columns = [desc[0] for desc in cursor.description]
        print(columns)
        for row in cursor.fetchall():
            print(row)
else:
    print("ERROR: spatial_clusters table does not exist")

    # 列出所有包含 spatial 的表
    print("\n=== 包含 'spatial' 的表 ===")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%spatial%'")
    for row in cursor.fetchall():
        print(f"  - {row[0]}")

conn.close()
