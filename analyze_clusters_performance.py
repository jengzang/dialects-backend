import sqlite3
import time

db_path = "C:/Users/joengzaang/myfiles/server/fastapi/data/villages.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

run_id = "spatial_eps_05"

print("=== 数据量统计 ===")
cursor.execute("SELECT COUNT(*) FROM spatial_clusters WHERE run_id = ?", (run_id,))
total = cursor.fetchone()[0]
print(f"总记录数: {total:,}")

cursor.execute("SELECT COUNT(*) FROM spatial_clusters WHERE run_id = ? AND cluster_id = -1", (run_id,))
noise = cursor.fetchone()[0]
print(f"噪声点 (cluster_id=-1): {noise:,}")

valid = total - noise
print(f"有效聚类记录: {valid:,}")

cursor.execute("SELECT COUNT(DISTINCT cluster_id) FROM spatial_clusters WHERE run_id = ? AND cluster_id != -1", (run_id,))
unique_clusters = cursor.fetchone()[0]
print(f"不同的聚类数: {unique_clusters:,}")

print("\n=== 聚类大小分布 ===")
cursor.execute("""
    SELECT cluster_id, COUNT(*) as size
    FROM spatial_clusters
    WHERE run_id = ? AND cluster_id != -1
    GROUP BY cluster_id
    ORDER BY size DESC
    LIMIT 10
""", (run_id,))
print("Top 10 最大聚类:")
for row in cursor.fetchall():
    print(f"  Cluster {row[0]}: {row[1]:,} 个村庄")

print("\n=== 查询性能测试 ===")

# 测试1: 获取所有记录(无过滤)
query1 = """
    SELECT
        cluster_id,
        cluster_size,
        centroid_lon,
        centroid_lat,
        avg_distance_km
    FROM spatial_clusters
    WHERE run_id = ?
    ORDER BY cluster_id
"""
start = time.time()
cursor.execute(query1, (run_id,))
results1 = cursor.fetchall()
elapsed1 = time.time() - start
print(f"查询所有记录 ({len(results1):,} 条): {elapsed1:.4f}s")

# 测试2: 过滤噪声点
query2 = """
    SELECT
        cluster_id,
        cluster_size,
        centroid_lon,
        centroid_lat,
        avg_distance_km
    FROM spatial_clusters
    WHERE run_id = ? AND cluster_id != -1
    ORDER BY cluster_id
"""
start = time.time()
cursor.execute(query2, (run_id,))
results2 = cursor.fetchall()
elapsed2 = time.time() - start
print(f"过滤噪声点后 ({len(results2):,} 条): {elapsed2:.4f}s")

# 测试3: 限制100条
query3 = """
    SELECT
        cluster_id,
        cluster_size,
        centroid_lon,
        centroid_lat,
        avg_distance_km
    FROM spatial_clusters
    WHERE run_id = ? AND cluster_id != -1
    ORDER BY cluster_id
    LIMIT 100
"""
start = time.time()
cursor.execute(query3, (run_id,))
results3 = cursor.fetchall()
elapsed3 = time.time() - start
print(f"限制100条 ({len(results3):,} 条): {elapsed3:.4f}s")

print("\n=== 性能对比 ===")
print(f"返回所有记录比限制100条慢 {elapsed2/elapsed3:.1f}x")

conn.close()
