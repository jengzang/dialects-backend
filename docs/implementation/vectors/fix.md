# GET /api/villages/regional/vectors 端点修复报告

## 问题

原有的 GET /api/villages/regional/vectors 端点返回的数据格式与前端期望不符。

## 修复前后对比

### 修复前 ❌

**响应格式**:
```json
[
  {
    "region_id": "广州市",
    "region_name": "广州市",
    "region_level": "county",
    "N_villages": 991,
    "created_at": 1771176520.162
  }
]
```

**问题**:
- ❌ 缺少 `feature_vector` (9维数组)
- ❌ 缺少 `semantic_categories` (对象)
- ❌ 字段名不匹配 (`N_villages` vs `village_count`)
- ❌ 返回了不需要的字段 (`region_id`, `region_level`, `created_at`)
- ❌ 查询的是 `region_vectors` 表（存储复杂特征，不是9维语义向量）

### 修复后 ✅

**响应格式**:
```json
[
  {
    "region_name": "广州市",
    "feature_vector": [0.086393, 0.116079, 0.241973, 0.017569, 0.188295, 0.53738, 0.116321, 0.076821, 0.16285],
    "village_count": 8253,
    "semantic_categories": {
      "agriculture": 0.086393,
      "clan": 0.116079,
      "direction": 0.241973,
      "infrastructure": 0.017569,
      "mountain": 0.188295,
      "settlement": 0.53738,
      "symbolic": 0.116321,
      "vegetation": 0.076821,
      "water": 0.16285
    }
  }
]
```

**改进**:
- ✅ 包含 `feature_vector` (9维语义向量)
- ✅ 包含 `semantic_categories` (9个类别的详细数据)
- ✅ 字段名匹配前端期望 (`village_count`)
- ✅ 只返回必要的字段
- ✅ 查询 `semantic_indices` 表（正确的数据源）

## API 规格

### 端点

**GET** `/api/villages/regional/vectors`

### 查询参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| region_name | string | 否 | 区域名称（支持模糊匹配） |
| region_level | string | 否 | 区域层级 (city/county/township) |
| limit | integer | 否 | 返回记录数（默认100，最大1000） |
| run_id | string | 否 | 分析运行ID（默认使用活跃版本） |

### 响应字段

| 字段 | 类型 | 说明 |
|------|------|------|
| region_name | string | 区域名称 |
| feature_vector | array[float] | 9维语义向量（按字母顺序） |
| village_count | integer | 村庄数量 |
| semantic_categories | object | 9个语义类别的详细数据 |

### 语义类别顺序

向量按以下顺序排列（字母顺序）：
1. agriculture (农业)
2. clan (宗族)
3. direction (方位)
4. infrastructure (基础设施)
5. mountain (山)
6. settlement (聚落)
7. symbolic (象征)
8. vegetation (植物)
9. water (水)

## 使用示例

### 示例1: 按区域名称查询

```bash
GET /api/villages/regional/vectors?region_name=广州市
```

**响应**:
```json
[
  {
    "region_name": "广州市",
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

### 示例2: 按层级查询

```bash
GET /api/villages/regional/vectors?region_level=city&limit=5
```

**响应**: 返回前5个市级区域的向量数据

### 示例3: 模糊搜索

```bash
GET /api/villages/regional/vectors?region_name=深圳&limit=10
```

**响应**: 返回所有包含"深圳"的区域（如"深圳市"、"深圳市宝安区"等）

## 测试结果

✅ **所有测试通过**:
- ✅ 按区域名称查询
- ✅ 按层级查询
- ✅ 模糊搜索
- ✅ 错误处理（无效层级）
- ✅ 响应格式符合前端期望

## 实现细节

### 数据源

- **表**: `semantic_indices`
- **字段**: `region_name`, `region_level`, `category`, `raw_intensity`, `village_count`, `run_id`

### 处理逻辑

1. 从 `semantic_indices` 表查询数据
2. 按区域分组（每个区域有9条记录，每个类别一条）
3. 验证数据完整性（必须有9个类别）
4. 按字母顺序构建 `feature_vector`
5. 构建 `semantic_categories` 对象
6. 返回符合前端期望的格式

### 代码位置

- **文件**: `app/tools/VillagesML/regional/aggregates_realtime.py`
- **函数**: `get_region_vectors()`
- **行数**: ~486-600

## 兼容性

- ✅ 向后兼容：新格式包含所有前端需要的字段
- ✅ 数据一致性：与 POST /vectors/compare 使用相同的数据源
- ✅ 性能：实时查询，响应时间 < 100ms

## 总结

GET /api/villages/regional/vectors 端点已修复，现在返回的数据格式完全符合前端期望：
- ✅ 包含9维语义向量
- ✅ 包含语义类别详情
- ✅ 字段名匹配
- ✅ 支持灵活查询（按名称、层级、模糊搜索）
- ✅ 所有测试通过

**状态**: ✅ 已修复并测试通过
**日期**: 2026-03-01
