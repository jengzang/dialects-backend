import sqlite3

db_path = "C:/Users/joengzaang/myfiles/server/fastapi/data/villages.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=== 所有可用的 run_id 及其统计 ===\n")

cursor.execute("""
    SELECT
        run_id,
        COUNT(*) as total_clusters,
        COUNT(DISTINCT cluster_id) as unique_clusters,
        MIN(cluster_id) as min_cluster_id,
        MAX(cluster_id) as max_cluster_id,
        AVG(cluster_size) as avg_cluster_size,
        MAX(cluster_size) as max_cluster_size
    FROM spatial_clusters
    GROUP BY run_id
    ORDER BY run_id
""")

results = cursor.fetchall()

for row in results:
    run_id, total, unique, min_id, max_id, avg_size, max_size = row
    print(f"run_id: {run_id}")
    print(f"  总记录数: {total:,}")
    print(f"  不同聚类数: {unique:,}")
    print(f"  聚类ID范围: {min_id} ~ {max_id}")
    print(f"  平均聚类大小: {avg_size:.1f}")
    print(f"  最大聚类大小: {int(max_size):,}")
    print()

# 检查是否有 analysis_runs 或其他元数据表
print("=== 检查是否有 run_id 元数据表 ===")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%run%'")
tables = cursor.fetchall()
for table in tables:
    print(f"  - {table[0]}")

conn.close()
