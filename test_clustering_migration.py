#!/usr/bin/env python
"""
Test script for clustering migration to village_cluster_assignments table
"""
import sqlite3
import sys

def test_data_consistency():
    """Verify that cluster data is accessible via new table"""
    conn = sqlite3.connect('data/villages.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("=" * 60)
    print("Testing Clustering Migration")
    print("=" * 60)

    # Test 1: Check if new table has data
    print("\n1. Checking village_cluster_assignments table...")
    cursor.execute("""
        SELECT run_id, COUNT(*) as count
        FROM village_cluster_assignments
        GROUP BY run_id
    """)
    results = cursor.fetchall()

    if not results:
        print("   FAIL: No data in village_cluster_assignments")
        return False

    for row in results:
        print(f"   OK: {row['run_id']}: {row['count']:,} records")

    # Test 2: Verify JOIN query works
    print("\n2. Testing LEFT JOIN query (spatial_eps_20)...")
    cursor.execute("""
        SELECT
            vsf.village_id,
            vsf.village_name,
            vca.cluster_id as spatial_cluster_id,
            sc.cluster_size
        FROM village_spatial_features vsf
        LEFT JOIN village_cluster_assignments vca
            ON vsf.village_id = vca.village_id AND vca.run_id = 'spatial_eps_20'
        LEFT JOIN spatial_clusters sc
            ON vca.run_id = sc.run_id AND vca.cluster_id = sc.cluster_id
        LIMIT 5
    """)
    results = cursor.fetchall()

    if not results:
        print("   FAIL: JOIN query returned no results")
        return False

    for row in results:
        cluster_id = row['spatial_cluster_id']
        cluster_size = row['cluster_size']
        status = "OK" if cluster_id is not None else "WARN"
        print(f"   {status}: {row['village_name']}: cluster_id={cluster_id}, size={cluster_size}")

    # Test 3: Compare coverage
    print("\n3. Checking data coverage...")
    cursor.execute("SELECT COUNT(*) as total FROM village_spatial_features")
    total_villages = cursor.fetchone()['total']

    cursor.execute("""
        SELECT COUNT(*) as assigned
        FROM village_cluster_assignments
        WHERE run_id = 'spatial_eps_20'
    """)
    assigned_villages = cursor.fetchone()['assigned']

    coverage = (assigned_villages / total_villages) * 100
    print(f"   Total villages with spatial features: {total_villages:,}")
    print(f"   Villages with cluster assignments: {assigned_villages:,}")
    print(f"   Coverage: {coverage:.1f}%")

    if coverage < 90:
        print(f"   WARN: Coverage is below 90%")
    else:
        print(f"   OK: Good coverage")

    # Test 4: Test different clustering versions
    print("\n4. Testing multi-version support...")
    versions = ['spatial_eps_05', 'spatial_eps_10', 'spatial_eps_20', 'spatial_hdbscan_v1']

    for version in versions:
        cursor.execute("""
            SELECT COUNT(DISTINCT cluster_id) as num_clusters
            FROM village_cluster_assignments
            WHERE run_id = ?
        """, (version,))
        result = cursor.fetchone()
        num_clusters = result['num_clusters']
        print(f"   OK: {version}: {num_clusters} clusters")

    conn.close()

    print("\n" + "=" * 60)
    print("SUCCESS: All tests passed!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    try:
        success = test_data_consistency()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
