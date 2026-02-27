"""
测试township级别聚类是否正确返回镇级数据
"""
import requests
import json

API_URL = "http://127.0.0.1:5000/api/villages/compute/clustering/run"

# 测试township级别
request_data = {
    "algorithm": "kmeans",
    "k": 5,
    "region_level": "township",
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

print("测试township级别聚类...")
print("=" * 80)

try:
    response = requests.post(API_URL, json=request_data, timeout=30)
    result = response.json()

    print(f"✅ 请求成功")
    print(f"区域数量: {result['n_regions']}")
    print(f"聚类数: {result.get('metrics', {}).get('n_clusters', result.get('k'))}")
    print(f"\n前10个区域:")

    for i, assignment in enumerate(result['assignments'][:10]):
        print(f"  {i+1}. {assignment['region_name']} → cluster {assignment['cluster_id']}")

    # 验证是否是镇级数据
    sample_names = [a['region_name'] for a in result['assignments'][:5]]

    print(f"\n验证:")
    if any('镇' in name or '街道' in name or '乡' in name for name in sample_names):
        print("  ✅ 返回的是镇级数据(包含'镇'/'街道'/'乡')")
    else:
        print("  ⚠️  返回的可能不是镇级数据")
        print(f"  样本名称: {sample_names}")

except Exception as e:
    print(f"❌ 错误: {str(e)}")

print("=" * 80)
