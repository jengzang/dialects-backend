# 子集比较 API 参数格式调整

## 概述

`/api/villages/compute/subset/compare` 接口已更新，支持两种参数模式：

1. **village_ids 模式**（推荐）：直接传递村庄 ID 列表
2. **filter 模式**（向后兼容）：使用筛选条件

## 新的参数格式

### 使用 village_ids（推荐）

```json
{
  "group_a": {
    "label": "子集A (4107个村庄)",
    "village_ids": [71, 72, 73, 156, ...]
  },
  "group_b": {
    "label": "子集B (33201个村庄)",
    "village_ids": [1, 2, 3, 4, ...]
  },
  "analysis": {
    "semantic_distribution": true,
    "morphology_patterns": true,
    "statistical_test": "chi_square"
  }
}
```

### 使用 filter（向后兼容）

```json
{
  "group_a": {
    "label": "广州市村庄",
    "filter": {
      "cities": ["广州市"],
      "counties": [],
      "semantic_tags": [],
      "sample_size": 1000
    }
  },
  "group_b": {
    "label": "深圳市村庄",
    "filter": {
      "cities": ["深圳市"],
      "sample_size": 1000
    }
  },
  "analysis": {
    "semantic_distribution": true,
    "morphology_patterns": true
  }
}
```

### 混合模式

可以一个组使用 village_ids，另一个组使用 filter：

```json
{
  "group_a": {
    "label": "指定村庄",
    "village_ids": [1, 2, 3, 4, 5]
  },
  "group_b": {
    "label": "广州市村庄",
    "filter": {
      "cities": ["广州市"],
      "sample_size": 500
    }
  },
  "analysis": {
    "semantic_distribution": true
  }
}
```

## 参数说明

### ComparisonGroup

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| label | string | 是 | 组标签（1-50字符） |
| village_ids | int[] | 条件必填 | 村庄ID列表（推荐使用） |
| filter | SubsetFilter | 条件必填 | 筛选条件（向后兼容） |

**注意：**
- `village_ids` 和 `filter` 必须提供其中一个，不能同时提供
- `village_ids` 不能为空数组
- `village_ids` 最多支持 50,000 个村庄
- ID 格式会自动标准化（自动添加 `v_` 前缀）

### SubsetFilter（filter 模式）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| cities | string[] | 否 | 城市列表 |
| counties | string[] | 否 | 县区列表 |
| semantic_tags | string[] | 否 | 语义标签列表 |
| sample_size | int | 否 | 采样大小（100-10000） |

**注意：** `name_pattern` 字段已移除，不再支持

### analysis

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| semantic_distribution | boolean | true | 是否进行语义分布对比 |
| morphology_patterns | boolean | true | 是否进行形态学对比 |
| statistical_test | string | null | 统计检验方法（"chi_square"） |

## 响应格式

```json
{
  "comparison_id": "compare_1772476603",
  "group_a_size": 4107,
  "group_b_size": 33201,
  "execution_time_ms": 245,
  "semantic_comparison": [
    {
      "category": "水系",
      "group_a_count": 523,
      "group_a_pct": 0.127,
      "group_b_count": 4215,
      "group_b_pct": 0.127,
      "difference": 0.000
    }
  ],
  "morphology_comparison": [
    {
      "feature": "avg_name_length",
      "group_a_value": 3.45,
      "group_b_value": 3.52,
      "difference": -0.07
    }
  ],
  "significant_differences": [
    {
      "feature": "山地",
      "test": "chi_square",
      "statistic": 12.34,
      "p_value": 0.0004
    }
  ],
  "from_cache": false
}
```

## 优势对比

### village_ids 模式（推荐）

**优点：**
- ✅ 明确性：直接指定要比较的村庄
- ✅ 一致性：与 `/compute/features/extract` API 设计一致
- ✅ 简洁性：只传必要的 ID
- ✅ 可靠性：避免前后端筛选逻辑不一致
- ✅ 性能：批量查询优化，支持大规模数据

**适用场景：**
- 前端已经筛选出具体村庄列表
- 需要对比特定的村庄集合
- 需要精确控制对比的村庄

### filter 模式（向后兼容）

**优点：**
- ✅ 向后兼容：不影响现有代码
- ✅ 便捷性：适合简单的区域筛选

**适用场景：**
- 简单的城市/县区筛选
- 不需要精确控制村庄列表
- 快速原型开发

## 实现细节

### ID 格式标准化

后端会自动处理 ID 格式：
- 前端发送：`[1, 2, 3, 4, 5]`
- 后端查询：`['v_1', 'v_2', 'v_3', 'v_4', 'v_5']`

### 批量查询优化

为避免 SQLite 表达式树深度限制，使用分批查询：
- 每批最多 500 个 ID
- 自动合并所有批次结果

### 缓存机制

两种模式都支持缓存：
- 缓存键基于完整的请求参数
- 相同参数的请求会返回缓存结果
- `from_cache` 字段指示是否来自缓存

## 迁移指南

### 从 filter 迁移到 village_ids

**之前：**
```javascript
const payload = {
  group_a: {
    label: "子集A",
    filter: {
      cities: ["广州市"],
      semantic_tags: ["水系"],
      sample_size: 1000
    }
  },
  group_b: { ... }
}
```

**之后：**
```javascript
// 1. 前端先筛选出村庄列表
const villageIds = await filterVillages({
  cities: ["广州市"],
  semantic_tags: ["水系"],
  sample_size: 1000
});

// 2. 直接传递 ID 列表
const payload = {
  group_a: {
    label: `子集A (${villageIds.length}个村庄)`,
    village_ids: villageIds
  },
  group_b: { ... }
}
```

## 测试

运行测试脚本：

```bash
python test_subset_compare_new.py
```

测试覆盖：
- ✅ village_ids 模式
- ✅ filter 模式（向后兼容）
- ✅ 混合模式
- ✅ 参数验证错误

## 注意事项

1. **ID 格式**：前端可以发送纯数字 ID，后端会自动添加 `v_` 前缀
2. **数量限制**：单次最多支持 50,000 个村庄
3. **性能**：village_ids 模式性能更好，推荐使用
4. **向后兼容**：filter 模式仍然可用，不影响现有代码

## 相关 API

- `/api/villages/compute/features/extract` - 特征提取（使用相同的 village_ids 格式）
- `/api/villages/compute/subset/cluster` - 子集聚类（仍使用 filter 格式）

## 更新日期

2026-03-03
