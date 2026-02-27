# 新增聚类API端点使用指南

## 快速开始

所有新端点都需要登录认证，请先获取JWT token。

## 1. 字符倾向性聚类

基于字符使用模式对区域进行聚类。

### 端点
```
POST /api/villages/compute/clustering/character-tendency
```

### 请求示例
```bash
curl -X POST "http://localhost:5000/api/villages/compute/clustering/character-tendency" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "kmeans",
    "k": 3,
    "region_level": "city",
    "top_n_chars": 50,
    "tendency_metric": "z_score"
  }'
```

### 参数说明
- `algorithm`: 聚类算法 (kmeans/dbscan/gmm)
- `k`: 聚类数量 (2-20，DBSCAN不需要)
- `region_level`: 区域级别 (city/county/township)
- `region_filter`: 可选，过滤特定区域
- `top_n_chars`: 每个区域选择top N字符 (10-500)
- `tendency_metric`: 倾向性指标 (z_score/lift/log_odds)
- `preprocessing`: 预处理配置
- `random_state`: 随机种子 (默认42)

### 响应示例
```json
{
  "run_id": "char_tendency_1709123456",
  "algorithm": "kmeans",
  "k": 3,
  "n_regions": 21,
  "tendency_metric": "z_score",
  "top_n_chars": 50,
  "execution_time_ms": 450,
  "metrics": {
    "silhouette_score": 0.456,
    "davies_bouldin_index": 0.789,
    "calinski_harabasz_score": 123.45
  },
  "assignments": [
    {"region_name": "广州市", "cluster_id": 0},
    {"region_name": "深圳市", "cluster_id": 1}
  ],
  "cluster_profiles": [
    {
      "cluster_id": 0,
      "region_count": 8,
      "regions": ["广州市", "佛山市", "..."],
      "centroid_norm": 12.34,
      "intra_cluster_variance": 0.56
    }
  ],
  "from_cache": false
}
```

## 2. 采样村庄聚类

对28.5万村庄进行智能采样后聚类。

### 端点
```
POST /api/villages/compute/clustering/sampled-villages
```

### 请求示例
```bash
curl -X POST "http://localhost:5000/api/villages/compute/clustering/sampled-villages" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "kmeans",
    "k": 5,
    "sampling_strategy": "stratified",
    "sample_size": 5000,
    "filter": {
      "cities": ["广州市", "深圳市"]
    }
  }'
```

### 参数说明
- `algorithm`: 聚类算法 (kmeans/dbscan/gmm)
- `k`: 聚类数量 (2-20)
- `sampling_strategy`: 采样策略
  - `random`: 随机采样
  - `stratified`: 按县分层采样（保持区域分布）
  - `spatial`: 空间网格采样（地理均匀）
- `sample_size`: 采样大小 (100-10000)
- `filter`: 可选过滤器
  - `cities`: 城市列表
  - `counties`: 县区列表
  - `semantic_tags`: 语义标签
- `features`: 特征配置
- `preprocessing`: 预处理配置
- `random_state`: 随机种子

### 响应示例
```json
{
  "run_id": "sampled_villages_1709123456",
  "algorithm": "kmeans",
  "k": 5,
  "original_village_count": 285860,
  "sampled_village_count": 5000,
  "sampling_strategy": "stratified",
  "execution_time_ms": 2340,
  "metrics": {
    "silhouette_score": 0.234,
    "davies_bouldin_index": 1.234,
    "calinski_harabasz_score": 456.78
  },
  "assignments": [
    {"village_name": "石牌村", "cluster_id": 0},
    {"village_name": "猎德村", "cluster_id": 1}
  ],
  "cluster_profiles": [...],
  "from_cache": false
}
```

## 3. 空间感知聚类

对已有的空间聚类结果进行二次聚类（元聚类）。

### 端点
```
POST /api/villages/compute/clustering/spatial-aware
```

### 请求示例
```bash
curl -X POST "http://localhost:5000/api/villages/compute/clustering/spatial-aware" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "kmeans",
    "k": 5,
    "spatial_run_id": "spatial_eps_20",
    "features": {
      "use_semantic_profile": true,
      "use_naming_patterns": true,
      "use_geographic": true,
      "use_cluster_size": true
    }
  }'
```

### 参数说明
- `algorithm`: 聚类算法 (kmeans/dbscan/gmm)
- `k`: 聚类数量 (2-20)
- `spatial_run_id`: 空间聚类运行ID
  - `spatial_eps_20`: DBSCAN eps=20 (253个聚类)
  - `spatial_eps_50`: DBSCAN eps=50
  - `spatial_hdbscan_v1`: HDBSCAN (7213个聚类)
  - 其他可用ID见 `/api/villages/admin/run-ids`
- `features`: 特征配置
  - `use_semantic_profile`: 使用语义特征
  - `use_naming_patterns`: 使用命名模式
  - `use_geographic`: 使用地理坐标
  - `use_cluster_size`: 使用聚类大小
- `preprocessing`: 预处理配置
- `random_state`: 随机种子

### 响应示例
```json
{
  "run_id": "spatial_aware_1709123456",
  "algorithm": "kmeans",
  "k": 5,
  "spatial_run_id": "spatial_eps_20",
  "n_spatial_clusters": 253,
  "execution_time_ms": 890,
  "metrics": {
    "silhouette_score": 0.345,
    "davies_bouldin_index": 0.987,
    "calinski_harabasz_score": 234.56
  },
  "assignments": [
    {"spatial_cluster_id": 1, "meta_cluster_id": 0},
    {"spatial_cluster_id": 2, "meta_cluster_id": 1}
  ],
  "cluster_profiles": [...],
  "from_cache": false
}
```

## 4. 层次聚类

展示市→县→镇的嵌套聚类结构。

### 端点
```
POST /api/villages/compute/clustering/hierarchical
```

### 请求示例
```bash
curl -X POST "http://localhost:5000/api/villages/compute/clustering/hierarchical" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "algorithm": "kmeans",
    "k_city": 3,
    "k_county": 5,
    "k_township": 10
  }'
```

### 参数说明
- `algorithm`: 聚类算法 (kmeans/gmm，不支持DBSCAN)
- `k_city`: 市级聚类数 (2-10)
- `k_county`: 县级聚类数 (2-15)
- `k_township`: 镇级聚类数 (2-30)
- `features`: 特征配置
- `preprocessing`: 预处理配置
- `random_state`: 随机种子

### 响应示例
```json
{
  "run_id": "hierarchical_1709123456",
  "algorithm": "kmeans",
  "k_city": 3,
  "k_county": 5,
  "k_township": 10,
  "execution_time_ms": 5670,
  "tree": [
    {
      "level": "city",
      "region_name": "广州市",
      "cluster_id": 0,
      "children": [
        {
          "level": "county",
          "region_name": "天河区",
          "cluster_id": 0,
          "parent_cluster_id": 0,
          "children": [
            {
              "level": "township",
              "region_name": "石牌街道",
              "cluster_id": 0,
              "parent_cluster_id": 0
            }
          ]
        }
      ]
    }
  ],
  "metrics": {
    "city_metrics": {
      "silhouette_score": 0.456,
      "davies_bouldin_index": 0.789,
      "calinski_harabasz_score": 123.45
    },
    "county_clusters_count": 3,
    "township_clusters_count": 8
  },
  "from_cache": false
}
```

## 通用特性

### 缓存
所有端点都支持缓存（TTL: 1小时）。相同参数的请求会直接返回缓存结果：
```json
{
  "from_cache": true,
  ...
}
```

### 超时控制
- 字符倾向性/采样村庄/空间感知: 5秒超时
- 层次聚类: 8秒超时

超时会返回408错误：
```json
{
  "detail": "Computation timeout after 5 seconds"
}
```

### 错误处理
- 401: 未登录
- 408: 超时
- 422: 参数验证失败
- 500: 服务器错误

### 预处理配置
所有端点都支持预处理配置：
```json
{
  "preprocessing": {
    "standardize": true,
    "use_pca": true,
    "pca_n_components": 50
  }
}
```

### 特征配置
区域级聚类的特征配置：
```json
{
  "features": {
    "use_semantic": true,
    "use_morphology": true,
    "use_diversity": true,
    "top_n_suffix2": 100,
    "top_n_suffix3": 100
  }
}
```

## Python客户端示例

```python
import requests

class VillagesMLClient:
    def __init__(self, base_url, token):
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {token}"}

    def character_tendency_clustering(self, **params):
        url = f"{self.base_url}/api/villages/compute/clustering/character-tendency"
        response = requests.post(url, json=params, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def sampled_village_clustering(self, **params):
        url = f"{self.base_url}/api/villages/compute/clustering/sampled-villages"
        response = requests.post(url, json=params, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def spatial_aware_clustering(self, **params):
        url = f"{self.base_url}/api/villages/compute/clustering/spatial-aware"
        response = requests.post(url, json=params, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def hierarchical_clustering(self, **params):
        url = f"{self.base_url}/api/villages/compute/clustering/hierarchical"
        response = requests.post(url, json=params, headers=self.headers)
        response.raise_for_status()
        return response.json()

# 使用示例
client = VillagesMLClient("http://localhost:5000", "YOUR_TOKEN")

# 字符倾向性聚类
result = client.character_tendency_clustering(
    algorithm="kmeans",
    k=3,
    region_level="city",
    top_n_chars=50,
    tendency_metric="z_score"
)

print(f"聚类完成: {result['n_regions']} 个区域, {result['k']} 个聚类")
print(f"轮廓系数: {result['metrics']['silhouette_score']:.3f}")
```

## 性能参考

| 端点 | 数据量 | 预期响应时间 |
|------|--------|--------------|
| 字符倾向性 (city) | 21点 | < 0.5s |
| 字符倾向性 (county) | 122点 | < 1s |
| 字符倾向性 (township) | 1580点 | 2-3s |
| 采样村庄 (5K) | 5000点 | 1-2s |
| 采样村庄 (10K) | 10000点 | 2-3s |
| 空间感知 (eps_20) | 253点 | < 1s |
| 空间感知 (hdbscan) | 7213点 | 3-4s |
| 层次聚类 | 21+122+1580点 | 5-8s |

## 常见问题

### Q: 如何选择采样策略？
- **random**: 最快，适合快速测试
- **stratified**: 保持区域分布，适合区域对比分析
- **spatial**: 地理均匀，适合空间分析

### Q: 如何选择倾向性指标？
- **z_score**: 标准化差异，适合跨区域对比
- **lift**: 提升度，适合发现强关联
- **log_odds**: 对数几率，适合稀疏数据

### Q: 层次聚类为什么这么慢？
层次聚类需要串行执行3层聚类（city → county → township），总时间约为各层之和。可以通过减少k值来加速。

### Q: 如何查看可用的spatial_run_id？
```bash
curl "http://localhost:5000/api/villages/admin/run-ids" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Q: 缓存如何清除？
```bash
curl -X DELETE "http://localhost:5000/api/villages/compute/clustering/cache"
```

## 相关文档

- [实现总结](./NEW_CLUSTERING_ENDPOINTS_IMPLEMENTATION.md)
- [测试脚本](../test_new_clustering_endpoints.py)
- [CLAUDE.md](../CLAUDE.md) - 项目整体文档
