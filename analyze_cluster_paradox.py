import sqlite3

db_path = "C:/Users/joengzaang/myfiles/server/fastapi/data/villages.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=== 详细分析三个 run_id 的聚类特征 ===\n")

for run_id in ['spatial_eps_03', 'spatial_eps_05', 'spatial_eps_10']:
    print(f"{'='*60}")
    print(f"run_id: {run_id}")
    print(f"{'='*60}")

    # 基本统计
    cursor.execute("""
        SELECT
            COUNT(*) as total_records,
            COUNT(DISTINCT cluster_id) as unique_clusters,
            AVG(cluster_size) as avg_size,
            MIN(cluster_size) as min_size,
            MAX(cluster_size) as max_size,
            SUM(cluster_size) as total_villages
        FROM spatial_clusters
        WHERE run_id = ?
    """, (run_id,))

    stats = cursor.fetchone()
    print(f"\n基本统计:")
    print(f"  记录数: {stats[0]:,}")
    print(f"  不同聚类数: {stats[1]:,}")
    print(f"  平均大小: {stats[2]:.1f}")
    print(f"  大小范围: {stats[3]} ~ {stats[4]:,}")
    print(f"  总村庄数: {stats[5]:,}")

    # 聚类大小分布
    cursor.execute("""
        SELECT
            CASE
                WHEN cluster_size = 1 THEN '单村聚类'
                WHEN cluster_size BETWEEN 2 AND 5 THEN '2-5村'
                WHEN cluster_size BETWEEN 6 AND 10 THEN '6-10村'
                WHEN cluster_size BETWEEN 11 AND 50 THEN '11-50村'
                WHEN cluster_size BETWEEN 51 AND 100 THEN '51-100村'
                ELSE '100+村'
            END as size_range,
            COUNT(*) as count
        FROM spatial_clusters
        WHERE run_id = ?
        GROUP BY size_range
        ORDER BY MIN(cluster_size)
    """, (run_id,))

    print(f"\n聚类大小分布:")
    for row in cursor.fetchall():
        print(f"  {row[0]:15} : {row[1]:,} 个聚类")

    # 空间分布
    cursor.execute("""
        SELECT
            AVG(avg_distance_km) as avg_dist,
            MIN(avg_distance_km) as min_dist,
            MAX(avg_distance_km) as max_dist
        FROM spatial_clusters
        WHERE run_id = ?
    """, (run_id,))

    dist = cursor.fetchone()
    print(f"\n聚类内平均距离:")
    print(f"  平均: {dist[0]:.2f} km")
    print(f"  范围: {dist[1]:.2f} ~ {dist[2]:.2f} km")

    # 检查是否有重复的 cluster_id
    cursor.execute("""
        SELECT cluster_id, COUNT(*) as cnt
        FROM spatial_clusters
        WHERE run_id = ?
        GROUP BY cluster_id
        HAVING cnt > 1
        LIMIT 5
    """, (run_id,))

    duplicates = cursor.fetchall()
    if duplicates:
        print(f"\n警告: 发现重复的 cluster_id!")
        for dup in duplicates:
            print(f"  cluster_id {dup[0]}: {dup[1]} 条记录")

    print()

# 检查表结构
print(f"{'='*60}")
print("表结构分析")
print(f"{'='*60}")
cursor.execute("PRAGMA table_info(spatial_clusters)")
print("\nspatial_clusters 表字段:")
for row in cursor.fetchall():
    print(f"  {row[1]:25} {row[2]:15}")

# 查看示例数据
print(f"\n{'='*60}")
print("示例数据 (spatial_eps_05)")
print(f"{'='*60}")
cursor.execute("""
    SELECT cluster_id, cluster_size, centroid_lon, centroid_lat, avg_distance_km
    FROM spatial_clusters
    WHERE run_id = 'spatial_eps_05'
    ORDER BY cluster_size DESC
    LIMIT 10
""")
print("\nTop 10 最大聚类:")
for row in cursor.fetchall():
    print(f"  Cluster {row[0]:5}: size={row[1]:5}, distance={row[4]:.2f}km")

conn.close()
