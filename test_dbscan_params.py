"""
DBSCAN参数测试脚本
用于快速测试不同参数组合的聚类效果
"""
import requests
import json

API_URL = "http://127.0.0.1:5000/api/villages/compute/clustering/run"

# 测试参数组合
test_cases = [
    {"eps": 0.8, "min_samples": 2, "desc": "较严格"},
    {"eps": 1.0, "min_samples": 2, "desc": "中等偏严"},
    {"eps": 1.2, "min_samples": 2, "desc": "中等"},
    {"eps": 1.5, "min_samples": 2, "desc": "中等偏松"},
    {"eps": 1.0, "min_samples": 3, "desc": "中等(min_samples=3)"},
]

base_request = {
    "algorithm": "dbscan",
    "region_level": "city",
    "features": {
        "use_semantic": True,
        "use_morphology": True,
        "use_diversity": True
    },
    "preprocessing": {
        "use_pca": True,
        "pca_n_components": 50,
        "standardize": True
    },
    "random_state": 42
}

print("=" * 80)
print("DBSCAN参数测试 - 21个城市")
print("=" * 80)

for test in test_cases:
    request_data = base_request.copy()
    request_data["dbscan_config"] = {
        "eps": test["eps"],
        "min_samples": test["min_samples"]
    }

    try:
        response = requests.post(API_URL, json=request_data, timeout=10)
        result = response.json()

        # 统计聚类分布
        cluster_counts = {}
        for assignment in result.get("assignments", []):
            cid = assignment["cluster_id"]
            cluster_counts[cid] = cluster_counts.get(cid, 0) + 1

        n_clusters = len([k for k in cluster_counts.keys() if k != -1])
        n_noise = cluster_counts.get(-1, 0)

        print(f"\n参数: eps={test['eps']}, min_samples={test['min_samples']} ({test['desc']})")
        print(f"  聚类数: {n_clusters}")
        print(f"  噪声点: {n_noise}")
        print(f"  聚类分布: {dict(sorted(cluster_counts.items()))}")

        metrics = result.get("metrics", {})
        if metrics.get("silhouette_score", 0) > 0:
            print(f"  轮廓系数: {metrics['silhouette_score']:.3f}")

        # 评估质量
        if n_clusters == 0:
            print("  ❌ 质量: 全是噪声点")
        elif n_clusters == 1:
            print("  ⚠️  质量: 只有1个聚类,无区分度")
        elif n_noise > len(result["assignments"]) * 0.3:
            print("  ⚠️  质量: 噪声点过多(>30%)")
        else:
            print(f"  ✅ 质量: 良好 ({n_clusters}个聚类)")

    except Exception as e:
        print(f"\n参数: eps={test['eps']}, min_samples={test['min_samples']}")
        print(f"  ❌ 错误: {str(e)}")

print("\n" + "=" * 80)
print("建议:")
print("  - 选择聚类数在2-5之间的参数")
print("  - 噪声点比例应该 < 30%")
print("  - 轮廓系数越高越好(>0.3为良好)")
print("=" * 80)
