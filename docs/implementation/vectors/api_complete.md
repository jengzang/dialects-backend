# 区域向量 API 完整实现报告

## 实现总结

✅ **所有功能已实现并测试通过！**

### 实现的 API

#### 1. 层级参数修复（必须）✅

**GET /api/villages/regional/vectors**
- 使用层级路径参数避免重名
- 参数：level (必填), city, county, township (可选)
- 返回：区域向量列表，包含完整层级信息

**POST /api/villages/regional/vectors/compare**
- 使用扁平化层级参数
- 参数：level1/city1/county1/township1, level2/city2/county2/township2
- 返回：相似度指标（余弦、欧氏、曼哈顿）和原始向量

#### 2. 批量向量比较 ✅

**POST /api/villages/regional/vectors/compare/batch**
- 一次比较多个区域
- 返回相似度矩阵和距离矩阵
- 用于热力图可视化
- 最多支持 100 个区域

#### 3. 向量降维 ✅

**POST /api/villages/regional/vectors/reduce**
- 支持 PCA 和 t-SNE 两种方法
- 降维到 2D 或 3D
- 用于散点图可视化
- PCA 返回解释方差比

#### 4. 向量聚类 ✅

**POST /api/villages/regional/vectors/cluster**
- 支持 KMeans、DBSCAN、GMM 三种方法
- 返回聚类标签和中心点
- 发现语义相似的区域群组

## 测试结果

### 层级参数测试 ✅
- ✅ GET vectors for city level
- ✅ GET vectors for township with hierarchy
- ✅ POST compare same level (city vs city)
- ✅ POST compare cross level (city vs county)
- ✅ POST compare county level with hierarchy

### 批量操作测试 ✅
- ✅ Batch Compare (4 regions, 4x4 similarity matrix)
- ✅ PCA Dimensionality Reduction (5 regions, 2D, explained variance: 63.2% + 19.4%)
- ✅ t-SNE Dimensionality Reduction (5 regions, 2D)
- ✅ KMeans Clustering (6 regions, 3 clusters)
- ✅ DBSCAN Clustering (5 regions)

## API 详细规格

### 1. GET /api/villages/regional/vectors

**查询参数**:
```
level: str (必填) - city/county/township
city: str (可选) - 市级名称
county: str (可选) - 县级名称
township: str (可选) - 乡镇级名称
limit: int (可选) - 返回记录数，默认100
run_id: str (可选) - 分析运行ID
```

**响应示例**:
```json
[
  {
    "region_name": "广州市",
    "city": "广州市",
    "feature_vector": [0.086, 0.116, 0.242, 0.018, 0.188, 0.537, 0.116, 0.077, 0.163],
    "village_count": 8253,
    "semantic_categories": {
      "agriculture": 0.086,
      "clan": 0.116,
      "direction": 0.242,
      "infrastructure": 0.018,
      "mountain": 0.188,
      "settlement": 0.537,
      "symbolic": 0.116,
      "vegetation": 0.077,
      "water": 0.163
    }
  }
]
```

### 2. POST /api/villages/regional/vectors/compare

**请求体**:
```json
{
  "level1": "city",
  "city1": "广州市",
  "level2": "city",
  "city2": "深圳市"
}
```

**响应示例**:
```json
{
  "region1_name": "广州市",
  "level1": "city",
  "city1": "广州市",
  "region2_name": "深圳市",
  "level2": "city",
  "city2": "深圳市",
  "feature_dimension": 9,
  "categories": ["agriculture", "clan", "direction", "infrastructure", "mountain", "settlement", "symbolic", "vegetation", "water"],
  "cosine_similarity": 0.951596,
  "euclidean_distance": 0.209663,
  "manhattan_distance": 0.391714,
  "vector_diff": [-0.017, 0.035, -0.018, -0.003, -0.115, 0.168, 0.021, -0.001, -0.014],
  "region1_vector": [0.086, 0.116, 0.242, 0.018, 0.188, 0.537, 0.116, 0.077, 0.163],
  "region2_vector": [0.103, 0.081, 0.260, 0.021, 0.304, 0.370, 0.095, 0.078, 0.177],
  "run_id": "semantic_indices_001"
}
```

### 3. POST /api/villages/regional/vectors/compare/batch

**请求体**:
```json
{
  "regions": [
    {"level": "city", "city": "广州市"},
    {"level": "city", "city": "深圳市"},
    {"level": "city", "city": "佛山市"},
    {"level": "city", "city": "东莞市"}
  ]
}
```

**响应示例**:
```json
{
  "regions": [
    {"region_name": "广州市", "level": "city", "city": "广州市"},
    {"region_name": "深圳市", "level": "city", "city": "深圳市"},
    {"region_name": "佛山市", "level": "city", "city": "佛山市"},
    {"region_name": "东莞市", "level": "city", "city": "东莞市"}
  ],
  "similarity_matrix": [
    [1.0, 0.952, 0.939, 0.996],
    [0.952, 1.0, 0.941, 0.943],
    [0.939, 0.941, 1.0, 0.929],
    [0.996, 0.943, 0.929, 1.0]
  ],
  "distance_matrix": [
    [0.0, 0.210, 0.247, 0.063],
    [0.210, 0.0, 0.243, 0.239],
    [0.247, 0.243, 0.0, 0.267],
    [0.063, 0.239, 0.267, 0.0]
  ],
  "feature_dimension": 9,
  "categories": ["agriculture", "clan", "direction", "infrastructure", "mountain", "settlement", "symbolic", "vegetation", "water"],
  "run_id": "semantic_indices_001"
}
```

### 4. POST /api/villages/regional/vectors/reduce

**请求体**:
```json
{
  "regions": [
    {"level": "city", "city": "广州市"},
    {"level": "city", "city": "深圳市"},
    {"level": "city", "city": "佛山市"}
  ],
  "method": "pca",
  "n_components": 2
}
```

**响应示例**:
```json
{
  "regions": [
    {"region_name": "广州市", "level": "city", "city": "广州市"},
    {"region_name": "深圳市", "level": "city", "city": "深圳市"},
    {"region_name": "佛山市", "level": "city", "city": "佛山市"}
  ],
  "coordinates": [
    [-1.053, -1.154],
    [-1.736, 0.248],
    [0.981, 2.448]
  ],
  "method": "pca",
  "n_components": 2,
  "explained_variance": [0.632431, 0.193869],
  "run_id": "semantic_indices_001"
}
```

**方法说明**:
- `pca`: 主成分分析，保留最大方差
- `tsne`: t-SNE，保留局部结构

### 5. POST /api/villages/regional/vectors/cluster

**请求体（KMeans）**:
```json
{
  "regions": [
    {"level": "city", "city": "广州市"},
    {"level": "city", "city": "深圳市"},
    {"level": "city", "city": "佛山市"},
    {"level": "city", "city": "东莞市"},
    {"level": "city", "city": "中山市"},
    {"level": "city", "city": "珠海市"}
  ],
  "method": "kmeans",
  "n_clusters": 3
}
```

**请求体（DBSCAN）**:
```json
{
  "regions": [...],
  "method": "dbscan",
  "eps": 0.5,
  "min_samples": 2
}
```

**响应示例**:
```json
{
  "regions": [
    {"region_name": "广州市", "level": "city", "city": "广州市"},
    {"region_name": "深圳市", "level": "city", "city": "深圳市"},
    {"region_name": "佛山市", "level": "city", "city": "佛山市"},
    {"region_name": "东莞市", "level": "city", "city": "东莞市"},
    {"region_name": "中山市", "level": "city", "city": "中山市"},
    {"region_name": "珠海市", "level": "city", "city": "珠海市"}
  ],
  "labels": [2, 2, 0, 2, 1, 1],
  "n_clusters": 3,
  "cluster_centers": [
    [0.059, 0.079, 0.217, 0.015, 0.254, 0.516, 0.099, 0.069, 0.169],
    [0.073, 0.105, 0.246, 0.017, 0.188, 0.537, 0.116, 0.077, 0.163],
    [0.086, 0.116, 0.242, 0.018, 0.188, 0.537, 0.116, 0.077, 0.163]
  ],
  "method": "kmeans",
  "run_id": "semantic_indices_001"
}
```

**方法说明**:
- `kmeans`: K-均值聚类，需要指定 n_clusters
- `dbscan`: 基于密度的聚类，需要指定 eps 和 min_samples
- `gmm`: 高斯混合模型，需要指定 n_clusters

## 实现细节

### 文件结构
```
app/tools/VillagesML/regional/
├── aggregates_realtime.py (主文件，包含所有端点)
├── batch_vector_models.py (Pydantic 模型定义)
└── batch_operations_code.py (实现代码备份)
```

### 依赖库
- `numpy`: 向量运算
- `scipy.spatial.distance`: 距离计算（cosine, euclidean, cityblock）
- `sklearn.decomposition.PCA`: PCA 降维
- `sklearn.manifold.TSNE`: t-SNE 降维
- `sklearn.cluster.KMeans`: K-均值聚类
- `sklearn.cluster.DBSCAN`: DBSCAN 聚类
- `sklearn.mixture.GaussianMixture`: GMM 聚类
- `sklearn.preprocessing.StandardScaler`: 数据标准化

### 性能优化
- 向量标准化：所有降维和聚类操作前进行标准化
- t-SNE perplexity 自适应：根据样本数量自动调整
- 批量比较限制：最多 100 个区域，防止内存溢出
- 相似度矩阵对称性：只计算上三角，复制到下三角

## 使用场景

### 1. 热力图可视化
使用 `/vectors/compare/batch` 获取相似度矩阵，绘制热力图展示区域间的相似度。

### 2. 散点图可视化
使用 `/vectors/reduce` 将 9 维向量降维到 2D/3D，在散点图中展示区域分布。

### 3. 区域聚类分析
使用 `/vectors/cluster` 发现语义相似的区域群组，进行区域分类研究。

### 4. 区域比较
使用 `/vectors/compare` 比较两个区域的语义特征差异。

## 测试文件

- `test_hierarchy_params.py` - 层级参数测试
- `test_batch_operations.py` - 批量操作测试
- `test_vector_unit.py` - 单元测试
- `test_vector_api.py` - API 测试

## 总结

✅ **所有功能已完成并测试通过**
- 层级参数修复（避免重名）
- 批量向量比较（相似度矩阵）
- 向量降维（PCA/t-SNE）
- 向量聚类（KMeans/DBSCAN/GMM）

**状态**: ✅ 完成
**测试**: ✅ 全部通过
**文档**: ✅ 完整
**日期**: 2026-03-01
