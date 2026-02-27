"""
测试镇级聚类是否返回完整路径
"""
import requests
import json

API_URL = "http://127.0.0.1:5000/api/villages/compute/clustering/run"

# 测试township级别聚类
request_data = {
    "algorithm": "kmeans",
    "k": 3,
    "region_level": "township",
    "region_filter": None,  # 不过滤,获取所有镇
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

print("测试镇级聚类 - 检查是否返回完整路径")
print("=" * 80)

try:
    response = requests.post(API_URL, json=request_data, timeout=30)
    result = response.json()

    print(f"✅ 请求成功")
    print(f"区域数量: {result['n_regions']}")
    print(f"聚类数: {result.get('k')}")

    print(f"\n前20个区域名称:")
    for i, assignment in enumerate(result['assignments'][:20]):
        region_name = assignment['region_name']
        cluster_id = assignment['cluster_id']

        # 检查是否包含完整路径
        has_full_path = ' > ' in region_name
        path_parts = region_name.split(' > ') if has_full_path else [region_name]

        status = "✅" if has_full_path else "❌"
        print(f"  {i+1}. {status} {region_name} → cluster {cluster_id}")

        if has_full_path and len(path_parts) == 3:
            print(f"      市: {path_parts[0]}, 县: {path_parts[1]}, 镇: {path_parts[2]}")

    # 统计
    all_names = [a['region_name'] for a in result['assignments']]
    with_path = sum(1 for name in all_names if ' > ' in name)
    without_path = len(all_names) - with_path

    print(f"\n统计:")
    print(f"  包含完整路径: {with_path}/{len(all_names)} ({with_path/len(all_names)*100:.1f}%)")
    print(f"  不包含路径: {without_path}/{len(all_names)}")

    # 检查是否有重名
    town_names = [name.split(' > ')[-1] if ' > ' in name else name for name in all_names]
    from collections import Counter
    duplicates = {name: count for name, count in Counter(town_names).items() if count > 1}

    if duplicates:
        print(f"\n重名的镇 (前5个):")
        for name, count in list(duplicates.items())[:5]:
            print(f"  {name}: {count}个")
            # 显示这些重名镇的完整路径
            matching = [a['region_name'] for a in result['assignments']
                       if a['region_name'].endswith(name)]
            for full_path in matching[:3]:
                print(f"    - {full_path}")
    else:
        print(f"\n✅ 没有重名的镇")

except Exception as e:
    print(f"❌ 错误: {str(e)}")
    import traceback
    traceback.print_exc()

print("=" * 80)
