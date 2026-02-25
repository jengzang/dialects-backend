import sqlite3

db_path = "C:/Users/joengzaang/myfiles/server/fastapi/data/villages.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=== spatial_clusters 表结构 ===")
cursor.execute("PRAGMA table_info(spatial_clusters)")
for row in cursor.fetchall():
    print(f"{row[1]:30} {row[2]:15}")

print("\n=== 示例数据 ===")
cursor.execute("SELECT * FROM spatial_clusters WHERE run_id = 'spatial_eps_05' LIMIT 3")
columns = [desc[0] for desc in cursor.description]
print(f"Columns: {columns}")
for row in cursor.fetchall():
    print(row)

print("\n=== 检查是否有村庄ID字段 ===")
cursor.execute("PRAGMA table_info(spatial_clusters)")
cols = [row[1] for row in cursor.fetchall()]
has_village_id = any('village' in col.lower() for col in cols)
print(f"包含村庄ID字段: {has_village_id}")

print("\n=== 检查主表结构 ===")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%村%'")
village_tables = cursor.fetchall()
print("包含'村'的表:")
for table in village_tables:
    print(f"  - {table[0]}")

conn.close()
