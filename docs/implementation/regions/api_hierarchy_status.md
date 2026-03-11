# VillagesML API 层级查询状态报告

## 概述

本文档总结了 VillagesML 模块中所有 API 的层级查询实现状态，以及是否正确处理东莞市/中山市（无县级）的特殊情况。

## 1. 已使用完整层级的 API（但未处理东莞市/中山市）

这些 API 已经使用了 `city`, `county`, `township` 参数，但**没有**处理东莞市/中山市 county 为 NULL 的情况：

### ✅ 字符分析模块
1. **`/character/frequency/regional`** (character/frequency.py:60-130)
   - 表：char_regional_analysis ✓
   - 参数：city, county, township, region_name
   - 问题：未处理 county IS NULL

2. **`/character/tendency/by-region`** (character/tendency.py:15-86)
   - 表：char_regional_analysis ✓
   - 参数：city, county, township, region_name
   - 问题：未处理 county IS NULL

### ✅ 模式分析模块
3. **`/patterns/frequency/regional`** (patterns/__init__.py:67-141)
   - 表：pattern_regional_analysis ✓
   - 参数：city, county, township, region_name
   - 问题：未处理 county IS NULL

4. **`/patterns/tendency`** (patterns/__init__.py:144-225)
   - 表：pattern_regional_analysis ✓
   - 参数：city, county, township, region_name
   - 问题：未处理 county IS NULL

### ✅ N-gram 分析模块
5. **`/ngrams/regional`** (ngrams/frequency.py:105-259)
   - 表：regional_ngram_frequency ✓
   - 参数：city, county, township, region_name
   - 问题：未处理 county IS NULL

6. **`/ngrams/tendency`** (ngrams/frequency.py:359-623)
   - 表：ngram_tendency ✓
   - 参数：city, county, township, region_name
   - 问题：未处理 county IS NULL

### ✅ 语义分析模块
7. **`/semantic/category/vtf/regional`** (semantic/category.py:87-231)
   - 表：semantic_regional_analysis ✓
   - 参数：city, county, township, region_name
   - 问题：未处理 county IS NULL

8. **`/semantic/category/tendency`** (semantic/category.py - 需要确认行号)
   - 表：semantic_regional_analysis ✓
   - 参数：city, county, township, region_name
   - 问题：未处理 county IS NULL

### ✅ 区域相似度模块
9. **`/regions/similarity/search`** (regional/similarity.py:18-140)
   - 表：region_similarity ✓
   - 参数：city, county, township, region_name
   - 问题：未处理 county IS NULL

## 2. 需要修复的 API（未使用完整层级）

这些 API 目前只使用 `region_name`，需要添加完整层级支持：

### ❌ 语义组合模块
10. **`/semantic/indices`** (semantic/composition.py:244-313)
    - 表：semantic_indices / semantic_indices_detailed ✓
    - 当前参数：region_level, region_name
    - 需要添加：city, county, township

### ❌ 区域聚合模块
11. **`/regional/aggregates/city`** (regional/aggregates_realtime.py:56-69)
    - 表：semantic_indices ✓
    - 当前参数：city_name
    - 需要修改：改为 city（保持一致性）

12. **`/regional/aggregates/county`** (regional/aggregates_realtime.py:195-208)
    - 表：semantic_indices ✓
    - 当前参数：county_name, city_name
    - 需要添加：city, county（精确匹配）

13. **`/regional/aggregates/town`** (regional/aggregates_realtime.py:294-418)
    - 表：semantic_indices ✓
    - 当前参数：town_name, county_name
    - 需要添加：city, county, township

14. **`/regional/spatial-aggregates`** (regional/aggregates_realtime.py:421-480)
    - 表：region_spatial_aggregates ✓ (使用 "town" 列)
    - 当前参数：region_level, region_name
    - 需要添加：city, county, town

### ❌ 字符显著性模块
15. **`/character/significance/by-region`** (character/significance.py:73-127)
    - 表：tendency_significance ✓
    - 当前参数：region_name, region_level
    - 需要添加：city, county, township

## 3. 无需修改的 API（仅县级数据）

这些 API 查询的表只包含县级数据，县名在广东省内唯一，无需层级支持：

### ✅ 聚类模块
16. **`/clustering/assignments`** (clustering/assignments.py:17-67)
    - 表：cluster_assignments (仅县级，121 条)
    - 状态：✅ 无需修改

17. **`/clustering/assignments/by-region`** (clustering/assignments.py:70-112)
    - 表：cluster_assignments (仅县级)
    - 状态：✅ 无需修改

### ✅ 区域向量模块
18. **`/regional/vectors`** (regional/aggregates_realtime.py:483-527)
    - 表：region_vectors (仅县级，1,830 条)
    - 状态：✅ 无需修改

## 4. 东莞市/中山市特殊情况处理

### 问题描述
东莞市和中山市是地级市，但没有县级行政区划，直接管辖乡镇/街道。在数据库中：
- city = "东莞市" 或 "中山市"
- county = NULL 或 ""
- township = "石龙镇", "石牌街道" 等

### 当前状态
**所有 API 都未正确处理这种情况！**

### 需要的修复
对于所有使用层级查询的 API，当查询乡镇级数据时，如果提供了 city 但没有提供 county，应该：

```python
# 错误的查询（当前所有 API 的做法）
if city is not None:
    query += " AND city = ?"
    params.append(city)
if county is not None:
    query += " AND county = ?"
    params.append(county)
if township is not None:
    query += " AND township = ?"
    params.append(township)

# 正确的查询（需要添加）
if city is not None:
    query += " AND city = ?"
    params.append(city)
if county is not None:
    query += " AND county = ?"
    params.append(county)
elif city is not None and region_level == 'township':
    # 处理东莞市/中山市：有 city 但没有 county 的情况
    query += " AND (county IS NULL OR county = '')"
if township is not None:
    query += " AND township = ?"
    params.append(township)
```

## 5. 修复优先级

### 高优先级（必须修复）
1. `/semantic/indices` - 未使用层级，会混淆重名乡镇
2. `/regional/aggregates/town` - 未使用层级，会混淆重名乡镇
3. `/character/significance/by-region` - 未使用层级，会混淆重名乡镇
4. `/regional/spatial-aggregates` - 未使用层级，会混淆重名乡镇

### 中优先级（建议修复）
5. `/regional/aggregates/city` - 参数命名不一致
6. `/regional/aggregates/county` - 未使用精确层级匹配

### 低优先级（可选修复）
7-15. 已使用层级的 9 个 API - 添加东莞市/中山市处理逻辑

## 6. 修复计划

### 阶段 1：修复未使用层级的 API（6 个）
- semantic/composition.py: 1 个端点
- regional/aggregates_realtime.py: 4 个端点
- character/significance.py: 1 个端点

### 阶段 2：为所有层级 API 添加东莞市/中山市支持（15 个）
- character/frequency.py: 1 个端点
- character/tendency.py: 1 个端点
- patterns/__init__.py: 2 个端点
- ngrams/frequency.py: 2 个端点
- semantic/category.py: 2 个端点
- regional/similarity.py: 1 个端点
- 以及阶段 1 修复的 6 个端点

## 7. 测试用例

### 测试重名乡镇
```bash
# 应该只返回增城区的太平镇
GET /character/frequency/regional?region_level=township&city=广州市&county=增城区&township=太平镇

# 应该只返回花都区的太平镇
GET /character/frequency/regional?region_level=township&city=广州市&county=花都区&township=太平镇
```

### 测试东莞市/中山市
```bash
# 应该能正确查询东莞市的石龙镇
GET /character/frequency/regional?region_level=township&city=东莞市&township=石龙镇

# 应该能正确查询中山市的石岐街道
GET /character/frequency/regional?region_level=township&city=中山市&township=石岐街道
```

## 8. 总结

- **总 API 数**：18 个
- **需要修复（未使用层级）**：6 个
- **需要增强（添加东莞市/中山市支持）**：9 个
- **无需修改（仅县级数据）**：3 个

**关键发现**：所有 API 都未正确处理东莞市/中山市的特殊情况！
