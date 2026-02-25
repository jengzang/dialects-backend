"""
空间聚类数据验证脚本
Spatial Clustering Data Validation Script

用于验证重新生成的空间聚类数据质量
"""

import sqlite3
import requests
from typing import Dict, List

DB_PATH = "data/villages.db"
API_BASE = "http://localhost:5000/api/villages"


def validate_database():
    """验证数据库中的聚类数据"""
    print("=" * 80)
    print("数据库验证")
    print("=" * 80)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 检查 active_run_ids
    print("\n1. Active Run IDs:")
    cursor.execute("""
        SELECT analysis_type, run_id
        FROM active_run_ids
        WHERE analysis_type LIKE '%spatial%'
    """)
    for row in cursor.fetchall():
        print(f"   {row[0]}: {row[1]}")

    # 检查每个版本的聚类统计
    print("\n2. 聚类统计 (按 run_id):")
    cursor.execute("""
        SELECT
            run_id,
            COUNT(DISTINCT cluster_id) as cluster_count,
            SUM(cluster_size) as total_villages,
            MIN(cluster_size) as min_size,
            MAX(cluster_size) as max_size,
            AVG(cluster_size) as avg_size,
            MAX(cluster_size) * 100.0 / SUM(cluster_size) as max_cluster_pct
        FROM spatial_clusters
        GROUP BY run_id
        ORDER BY run_id
    """)

    print(f"\n{'Run ID':<30} {'聚类数':<10} {'总村庄':<10} {'最小':<8} {'最大':<10} {'平均':<10} {'最大占比':<10}")
    print("-" * 100)
    for row in cursor.fetchall():
        print(f"{row[0]:<30} {row[1]:<10} {row[2]:<10} {row[3]:<8} {row[4]:<10} {row[5]:<10.1f} {row[6]:<10.2f}%")

    # 检查噪声点
    print("\n3. 噪声点统计 (cluster_id = -1):")
    cursor.execute("""
        SELECT
            run_id,
            cluster_size as noise_count,
            cluster_size * 100.0 / (
                SELECT SUM(cluster_size)
                FROM spatial_clusters sc2
                WHERE sc2.run_id = sc.run_id
            ) as noise_pct
        FROM spatial_clusters sc
        WHERE cluster_id = -1
        ORDER BY run_id
    """)

    for row in cursor.fetchall():
        print(f"   {row[0]}: {row[1]:,} 个村庄 ({row[2]:.2f}%)")

    # 检查前10大聚类
    print("\n4. 前10大聚类 (spatial_eps_05):")
    cursor.execute("""
        SELECT
            cluster_id,
            cluster_size,
            centroid_lon,
            centroid_lat,
            avg_distance_km
        FROM spatial_clusters
        WHERE run_id = 'spatial_eps_05'
        ORDER BY cluster_size DESC
        LIMIT 10
    """)

    print(f"\n{'Cluster ID':<12} {'大小':<10} {'经度':<12} {'纬度':<12} {'平均距离':<12}")
    print("-" * 70)
    for row in cursor.fetchall():
        print(f"{row[0]:<12} {row[1]:<10} {row[2]:<12.4f} {row[3]:<12.4f} {row[4]:<12.3f} km")

    # 检查 cluster_assignments
    print("\n5. Cluster Assignments 统计:")
    cursor.execute("""
        SELECT
            region_level,
            COUNT(DISTINCT region_id) as regions,
            COUNT(DISTINCT cluster_id) as clusters
        FROM cluster_assignments
        GROUP BY region_level
    """)

    for row in cursor.fetchall():
        print(f"   {row[0]}: {row[1]} 个区域, {row[2]} 个聚类")

    # 检查 spatial_hotspots
    print("\n6. Spatial Hotspots 统计:")
    cursor.execute("""
        SELECT
            run_id,
            COUNT(*) as hotspot_count,
            AVG(density_score) as avg_density,
            AVG(village_count) as avg_villages
        FROM spatial_hotspots
        GROUP BY run_id
    """)

    for row in cursor.fetchall():
        print(f"   {row[0]}: {row[1]} 个热点, 平均密度 {row[2]:.3f}, 平均村庄数 {row[3]:.1f}")

    # 检查 spatial_tendency_integration
    print("\n7. Spatial-Tendency Integration 统计:")
    cursor.execute("""
        SELECT
            COUNT(*) as records,
            COUNT(DISTINCT character) as chars,
            COUNT(DISTINCT cluster_id) as clusters,
            AVG(spatial_coherence) as avg_coherence,
            SUM(CASE WHEN is_significant = 1 THEN 1 ELSE 0 END) as significant_count
        FROM spatial_tendency_integration
    """)

    row = cursor.fetchone()
    print(f"   总记录: {row[0]:,}")
    print(f"   不同字符: {row[1]}")
    print(f"   不同聚类: {row[2]}")
    print(f"   平均空间一致性: {row[3]:.3f}")
    print(f"   显著结果: {row[4]} ({row[4]/row[0]*100:.1f}%)")

    conn.close()


def validate_api():
    """验证 API 端点"""
    print("\n" + "=" * 80)
    print("API 验证")
    print("=" * 80)

    # 测试聚类列表
    print("\n1. 测试 /spatial/clusters (默认版本):")
    try:
        response = requests.get(f"{API_BASE}/spatial/clusters?limit=5")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ 返回 {len(data)} 条记录")
            if data:
                print(f"   示例: Cluster {data[0]['cluster_id']}, 大小 {data[0]['cluster_size']}")
        else:
            print(f"   ✗ 错误: {response.status_code} - {response.json()}")
    except Exception as e:
        print(f"   ✗ 异常: {e}")

    # 测试不同版本
    for run_id in ['spatial_eps_03', 'spatial_eps_05', 'spatial_eps_10']:
        print(f"\n2. 测试 /spatial/clusters (run_id={run_id}):")
        try:
            response = requests.get(f"{API_BASE}/spatial/clusters?run_id={run_id}&limit=5")
            if response.status_code == 200:
                data = response.json()
                print(f"   ✓ 返回 {len(data)} 条记录")
            else:
                print(f"   ✗ 错误: {response.status_code}")
        except Exception as e:
            print(f"   ✗ 异常: {e}")

    # 测试聚类汇总
    print(f"\n3. 测试 /spatial/clusters/summary:")
    try:
        response = requests.get(f"{API_BASE}/spatial/clusters/summary")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ Run ID: {data['run_id']}")
            print(f"   ✓ 总聚类数: {data['total_clusters']}")
            print(f"   ✓ 噪声点: {data['noise_points']}")
            print(f"   ✓ 聚类列表: {len(data['clusters'])} 个")
        else:
            print(f"   ✗ 错误: {response.status_code}")
    except Exception as e:
        print(f"   ✗ 异常: {e}")

    # 测试空间热点
    print(f"\n4. 测试 /spatial/hotspots:")
    try:
        response = requests.get(f"{API_BASE}/spatial/hotspots")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ 返回 {len(data)} 个热点")
            if data:
                print(f"   示例: 热点 {data[0]['hotspot_id']}, 密度 {data[0]['density_score']:.3f}")
        else:
            print(f"   ✗ 错误: {response.status_code}")
    except Exception as e:
        print(f"   ✗ 异常: {e}")

    # 测试整合分析
    print(f"\n5. 测试 /spatial/integration:")
    try:
        response = requests.get(f"{API_BASE}/spatial/integration?limit=5")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ 返回 {len(data)} 条记录")
            if data:
                print(f"   示例: 字符 '{data[0]['character']}', 聚类 {data[0]['cluster_id']}")
        else:
            print(f"   ✗ 错误: {response.status_code}")
    except Exception as e:
        print(f"   ✗ 异常: {e}")

    # 测试整合分析汇总
    print(f"\n6. 测试 /spatial/integration/summary:")
    try:
        response = requests.get(f"{API_BASE}/spatial/integration/summary")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ Run ID: {data['run_id']}")
            print(f"   ✓ 总记录: {data['overall']['total_records']}")
            print(f"   ✓ 不同字符: {data['overall']['unique_characters']}")
            print(f"   ✓ 不同聚类: {data['overall']['unique_clusters']}")
        else:
            print(f"   ✗ 错误: {response.status_code}")
    except Exception as e:
        print(f"   ✗ 异常: {e}")


def check_quality():
    """检查数据质量指标"""
    print("\n" + "=" * 80)
    print("数据质量检查")
    print("=" * 80)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for run_id in ['spatial_eps_03', 'spatial_eps_05', 'spatial_eps_10']:
        print(f"\n{run_id}:")

        # 聚类分布均匀性
        cursor.execute("""
            SELECT
                COUNT(DISTINCT cluster_id) as cluster_count,
                MAX(cluster_size) * 100.0 / SUM(cluster_size) as max_pct,
                SUM(CASE WHEN cluster_id IN (
                    SELECT cluster_id FROM spatial_clusters
                    WHERE run_id = ? AND cluster_id != -1
                    ORDER BY cluster_size DESC LIMIT 10
                ) THEN cluster_size ELSE 0 END) * 100.0 / SUM(cluster_size) as top10_pct
            FROM spatial_clusters
            WHERE run_id = ?
        """, (run_id, run_id))

        row = cursor.fetchone()
        cluster_count = row[0]
        max_pct = row[1]
        top10_pct = row[2]

        print(f"  聚类数: {cluster_count}")
        print(f"  最大聚类占比: {max_pct:.2f}% {'✓' if max_pct < 20 else '✗'}")
        print(f"  前10大聚类占比: {top10_pct:.2f}% {'✓' if top10_pct < 50 else '✗'}")

        # 噪声点比例
        cursor.execute("""
            SELECT
                cluster_size * 100.0 / (
                    SELECT SUM(cluster_size) FROM spatial_clusters WHERE run_id = ?
                ) as noise_pct
            FROM spatial_clusters
            WHERE run_id = ? AND cluster_id = -1
        """, (run_id, run_id))

        row = cursor.fetchone()
        if row:
            noise_pct = row[0]
            print(f"  噪声点比例: {noise_pct:.2f}%")

            # 根据 eps 判断是否合理
            if run_id == 'spatial_eps_03':
                status = '✓' if 30 <= noise_pct <= 40 else '⚠'
            elif run_id == 'spatial_eps_05':
                status = '✓' if 15 <= noise_pct <= 25 else '⚠'
            else:  # spatial_eps_10
                status = '✓' if 5 <= noise_pct <= 15 else '⚠'

            print(f"  噪声点比例评估: {status}")

    conn.close()


if __name__ == "__main__":
    print("\n空间聚类数据验证")
    print("=" * 80)
    print("执行时间:", __import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 80)

    # 1. 验证数据库
    validate_database()

    # 2. 检查数据质量
    check_quality()

    # 3. 验证 API
    validate_api()

    print("\n" + "=" * 80)
    print("验证完成")
    print("=" * 80)
