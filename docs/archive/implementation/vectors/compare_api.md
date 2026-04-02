# 区域向量比较 API 实现文档

## 概述

实现了区域语义特征向量比较 API，支持同层级和跨层级的区域比较。

## API 端点

**POST** `/api/villages/regional/vectors/compare`

## 功能特性

✅ **9维语义向量**
- agriculture (农业)
- clan (宗族)
- direction (方位)
- infrastructure (基础设施)
- mountain (山)
- settlement (聚落)
- symbolic (象征)
- vegetation (植物)
- water (水)

✅ **支持三个层级**
- city (市级) - 21个区域
- county (区县级) - 121个区域
- township (乡镇级) - 1,446个区域

✅ **四种相似度指标**
- 余弦相似度 (Cosine Similarity) - 值越大越相似，范围 0-1
- 欧氏距离 (Euclidean Distance) - 值越小越相似
- 曼哈顿距离 (Manhattan Distance) - 值越小越相似
- 向量差异 (Vector Difference) - region1 - region2

✅ **跨层级比较**
- 支持不同层级之间的比较（如 city vs county）
- 自动处理层级差异

## 请求格式

```json
{
  "region1": "广州市",
  "level1": "city",
  "region2": "天河区",
  "level2": "county",
  "run_id": "semantic_indices_001"  // 可选
}
```

### 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| region1 | string | 是 | 第一个区域名称 |
| level1 | string | 是 | 第一个区域层级 (city/county/township) |
| region2 | string | 是 | 第二个区域名称 |
| level2 | string | 是 | 第二个区域层级 (city/county/township) |
| run_id | string | 否 | 分析运行ID（默认使用活跃版本） |

## 响应格式

```json
{
  "region1": "广州市",
  "level1": "city",
  "region2": "天河区",
  "level2": "county",
  "feature_dimension": 9,
  "categories": [
    "agriculture", "clan", "direction", "infrastructure",
    "mountain", "settlement", "symbolic", "vegetation", "water"
  ],
  "cosine_similarity": 0.894233,
  "euclidean_distance": 0.792553,
  "manhattan_distance": 1.713680,
  "vector_diff": [0.012, -0.034, 0.056, ...],
  "region1_vector": [0.086, 0.116, 0.242, ...],
  "region2_vector": [0.074, 0.150, 0.186, ...],
  "run_id": "semantic_indices_001"
}
```

## 使用示例

### 示例1: 同层级比较（市 vs 市）

```bash
curl -X POST "http://localhost:5000/api/villages/regional/vectors/compare" \
  -H "Content-Type: application/json" \
  -d '{
    "region1": "广州市",
    "level1": "city",
    "region2": "深圳市",
    "level2": "city"
  }'
```

**结果**:
- 余弦相似度: 0.951596 (非常相似)
- 欧氏距离: 0.209663
- 曼哈顿距离: 0.391714

### 示例2: 跨层级比较（市 vs 县）

```bash
curl -X POST "http://localhost:5000/api/villages/regional/vectors/compare" \
  -H "Content-Type: application/json" \
  -d '{
    "region1": "广州市",
    "level1": "city",
    "region2": "天河区",
    "level2": "county"
  }'
```

**结果**:
- 余弦相似度: 0.894233 (较相似)
- 欧氏距离: 0.792553
- 曼哈顿距离: 1.713680

### 示例3: 跨层级比较（县 vs 乡镇）

```bash
curl -X POST "http://localhost:5000/api/villages/regional/vectors/compare" \
  -H "Content-Type: application/json" \
  -d '{
    "region1": "天河区",
    "level1": "county",
    "region2": "石牌街道",
    "level2": "township"
  }'
```

## 错误处理

### 404 - 区域不存在

```json
{
  "detail": "Region '不存在的城市' not found at level 'city'"
}
```

### 400 - 无效的层级参数

```json
{
  "detail": "Invalid level1: invalid_level. Must be one of: {'city', 'county', 'township'}"
}
```

### 500 - 数据不完整

```json
{
  "detail": "Incomplete data for region '某区域': expected 9 categories, got 7"
}
```

## 实现细节

### 数据源

- **表**: `semantic_indices`
- **字段**: `region_name`, `region_level`, `category`, `raw_intensity`, `run_id`
- **向量构建**: 按类别字母顺序提取 `raw_intensity` 值

### 计算方法

```python
# 1. 获取向量
vector1 = get_semantic_vector(region1, level1, run_id)
vector2 = get_semantic_vector(region2, level2, run_id)

# 2. 计算相似度
cosine_similarity = 1 - cosine(vector1, vector2)
euclidean_distance = euclidean(vector1, vector2)
manhattan_distance = cityblock(vector1, vector2)
vector_diff = vector1 - vector2
```

### 依赖库

- `numpy` - 向量运算
- `scipy.spatial.distance` - 距离计算
- `fastapi` - API 框架
- `pydantic` - 数据验证

## 测试结果

✅ **单元测试**: 所有测试通过
- 向量获取测试
- 相似度计算测试
- 跨层级比较测试

✅ **API 测试**: 所有测试通过
- 同层级比较测试
- 跨层级比较测试
- 错误处理测试

## 性能

- **响应时间**: < 100ms (实时计算)
- **数据完整性**: 100% (所有区域都有完整的9个类别数据)
- **并发支持**: 是（无状态设计）

## 文件位置

- **实现**: `app/tools/VillagesML/regional/aggregates_realtime.py`
- **测试**:
  - `test_vector_unit.py` - 单元测试
  - `test_vector_api.py` - API 测试
  - `test_vector_compare.py` - 集成测试

## 版本信息

- **实现日期**: 2026-03-01
- **版本**: 1.0.0
- **状态**: ✅ 已完成并测试通过
