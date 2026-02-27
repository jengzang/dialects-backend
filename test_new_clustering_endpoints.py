"""
测试新增聚类API端点

测试4个新端点：
1. /api/villages/compute/clustering/character-tendency
2. /api/villages/compute/clustering/sampled-villages
3. /api/villages/compute/clustering/spatial-aware
4. /api/villages/compute/clustering/hierarchical
"""

import requests
import json
import time

# 配置
BASE_URL = "http://localhost:5000"
TOKEN = None  # 需要替换为实际的JWT token


def test_character_tendency_clustering():
    """测试字符倾向性聚类"""
    print("\n=== 测试字符倾向性聚类 ===")

    url = f"{BASE_URL}/api/villages/compute/clustering/character-tendency"
    headers = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}

    payload = {
        "algorithm": "kmeans",
        "k": 3,
        "region_level": "city",
        "top_n_chars": 50,
        "tendency_metric": "z_score"
    }

    start = time.time()
    response = requests.post(url, json=payload, headers=headers)
    elapsed = time.time() - start

    print(f"状态码: {response.status_code}")
    print(f"响应时间: {elapsed:.2f}秒")

    if response.status_code == 200:
        result = response.json()
        print(f"✓ 成功: {result['n_regions']} 个区域, {result['k']} 个聚类")
        print(f"  执行时间: {result['execution_time_ms']}ms")
        print(f"  轮廓系数: {result['metrics']['silhouette_score']:.3f}")
    else:
        print(f"✗ 失败: {response.text}")


def test_sampled_village_clustering():
    """测试采样村庄聚类"""
    print("\n=== 测试采样村庄聚类 ===")

    url = f"{BASE_URL}/api/villages/compute/clustering/sampled-villages"
    headers = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}

    payload = {
        "algorithm": "kmeans",
        "k": 5,
        "sampling_strategy": "stratified",
        "sample_size": 5000,
        "filter": {
            "cities": ["广州市"]
        }
    }

    start = time.time()
    response = requests.post(url, json=payload, headers=headers)
    elapsed = time.time() - start

    print(f"状态码: {response.status_code}")
    print(f"响应时间: {elapsed:.2f}秒")

    if response.status_code == 200:
        result = response.json()
        print(f"✓ 成功: 原始 {result['original_village_count']} 村庄, 采样 {result['sampled_village_count']} 村庄")
        print(f"  执行时间: {result['execution_time_ms']}ms")
        print(f"  轮廓系数: {result['metrics']['silhouette_score']:.3f}")
    else:
        print(f"✗ 失败: {response.text}")


def test_spatial_aware_clustering():
    """测试空间感知聚类"""
    print("\n=== 测试空间感知聚类 ===")

    url = f"{BASE_URL}/api/villages/compute/clustering/spatial-aware"
    headers = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}

    payload = {
        "algorithm": "kmeans",
        "k": 5,
        "spatial_run_id": "spatial_eps_20"
    }

    start = time.time()
    response = requests.post(url, json=payload, headers=headers)
    elapsed = time.time() - start

    print(f"状态码: {response.status_code}")
    print(f"响应时间: {elapsed:.2f}秒")

    if response.status_code == 200:
        result = response.json()
        print(f"✓ 成功: {result['n_spatial_clusters']} 个空间聚类, {result['k']} 个元聚类")
        print(f"  执行时间: {result['execution_time_ms']}ms")
        print(f"  轮廓系数: {result['metrics']['silhouette_score']:.3f}")
    else:
        print(f"✗ 失败: {response.text}")


def test_hierarchical_clustering():
    """测试层次聚类"""
    print("\n=== 测试层次聚类 ===")

    url = f"{BASE_URL}/api/villages/compute/clustering/hierarchical"
    headers = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}

    payload = {
        "algorithm": "kmeans",
        "k_city": 3,
        "k_county": 5,
        "k_township": 10
    }

    start = time.time()
    response = requests.post(url, json=payload, headers=headers)
    elapsed = time.time() - start

    print(f"状态码: {response.status_code}")
    print(f"响应时间: {elapsed:.2f}秒")

    if response.status_code == 200:
        result = response.json()
        print(f"✓ 成功: 层次聚类完成")
        print(f"  执行时间: {result['execution_time_ms']}ms")
        print(f"  市级聚类: {result['k_city']}")
        print(f"  县级聚类: {result['k_county']}")
        print(f"  镇级聚类: {result['k_township']}")
        print(f"  树节点数: {len(result['tree'])}")
    else:
        print(f"✗ 失败: {response.text}")


def main():
    """运行所有测试"""
    print("=" * 60)
    print("新增聚类API端点测试")
    print("=" * 60)

    if not TOKEN:
        print("\n⚠️  警告: 未设置TOKEN，测试将失败（需要登录）")
        print("请在脚本中设置 TOKEN 变量为有效的JWT token")
        return

    # Phase 1 测试
    test_character_tendency_clustering()
    test_sampled_village_clustering()

    # Phase 2 测试
    test_spatial_aware_clustering()
    test_hierarchical_clustering()

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
