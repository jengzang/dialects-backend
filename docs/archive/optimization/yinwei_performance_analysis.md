# /api/YinWei 性能瓶颈分析报告

## 问题概述

`/api/YinWei` 是系统中**最慢的API**，在大规模查询时耗时可达 **6秒以上**。

## 性能测试结果

### 规模测试

| 规模 | 地点数 | 特征数 | 耗时 | 返回结果数 |
|------|--------|--------|------|-----------|
| 小规模 | 1 | 1 | 735ms | 20 |
| 中规模 | 2 | 2 | 1,441ms | 72 |
| 大规模 | 5 | 3 | **6,416ms** | 268 |

### 性能分解（5地点 × 3特征）

| 步骤 | 耗时 | 占比 | 说明 |
|------|------|------|------|
| 1. query_dialect_features | 890ms | 14% | 查询方言数据 |
| 2. 批量查询 characters.db | 未单独测量 | ~5% | 查询中古音数据 |
| 3. analyze_characters | **4,800ms** | **75%** | 分析汉字（调用268次） |
| 4. 其他开销 | 726ms | 11% | 地点匹配、数据组织 |
| **总计** | **6,416ms** | 100% | |

## 性能瓶颈分析

### 🔴 主要瓶颈：analyze_characters_from_cached_df

**问题：**
- 每个 `(地点, 特征, 特征值)` 组合都要调用一次
- 5地点 × 3特征 × 平均18个值 = **268次调用**
- 每次调用平均耗时 18ms
- 总耗时：268 × 18ms = **4,824ms**

**为什么慢？**

```python
def analyze_characters_from_cached_df(char_df, char_list, ...):
    # 1. 过滤汉字
    df = char_df[char_df["漢字"].isin(char_list)].copy()  # 慢

    # 2. 分组统计
    grouped = df.groupby(group_fields)  # 慢

    # 3. 处理多地位字
    for group_keys, group_df in grouped:
        poly_chars = group_df[group_df["多地位標記"] == "1"]["漢字"].unique()
        for hz in poly_chars:
            sub = df[(df["漢字"] == hz) & (df["多地位標記"] == "1")]  # 非常慢
            # 构建详细信息
```

**性能问题：**
1. **重复过滤**：每次调用都要过滤 `char_df`（5955行）
2. **重复分组**：每次都要 `groupby`
3. **嵌套循环**：处理多地位字时有多层循环
4. **DataFrame操作开销**：pandas操作在小数据集上效率低

### 🟡 次要瓶颈：query_dialect_features

**问题：**
- SQL查询：17ms（快）
- 数据处理：1,298ms（慢）

**为什么慢？**

```python
def query_dialect_features(locations, features, ...):
    # SQL查询很快
    df = pd.read_sql_query(query, conn)  # 17ms

    # 数据处理很慢
    for feature in features:
        sub_df = df[...].dropna(subset=[feature])
        for value in sorted(sub_df[feature].unique()):  # 慢
            chars = sub_df[sub_df[feature] == value]['漢字'].unique().tolist()

            # 处理多音字
            poly_df = sub_df[(sub_df['多音字'] == '1') & (sub_df[feature] == value)]
            for hz in poly_df['漢字'].unique():
                poly_dict[hz] = poly_df[poly_df['漢字'] == hz]['音節'].unique().tolist()
```

**性能问题：**
1. **多次过滤**：对每个特征值都要过滤 DataFrame
2. **重复查询**：多音字处理有嵌套循环
3. **pandas开销**：大量小规模的 DataFrame 操作

## 索引分析

### 当前索引使用

```sql
SELECT 簡稱, 漢字, 聲母, 韻母, 聲調, 音節, 多音字
FROM dialects
WHERE 簡稱 IN (...)
```

**执行计划：**
```
SEARCH dialects USING INDEX idx_dialects_abbr (簡稱=?)
```

**性能：**
- 扫描行数：9,795行（5个地点）
- SQL耗时：17ms
- **索引是正确的，不是瓶颈**

### 为什么不是索引问题？

1. **SQL查询很快**：17ms 对于扫描1万行是合理的
2. **没有更好的索引**：查询需要返回所有汉字，无法进一步优化
3. **瓶颈在应用层**：75%的时间花在Python数据处理上

## 优化方案

### 方案1：缓存优化（立即可行）✅

**问题：**
- 每次调用 `analyze_characters_from_cached_df` 都要重复过滤和分组

**解决方案：**
```python
# 预先按 group_fields 分组，避免重复计算
def pho2sta(...):
    # 批量查询 characters.db（已有）
    all_chars_df = ...

    # 【新增】预先按常用分组字段建立索引
    grouped_cache = {}
    for group_fields in [['母'], ['攝'], ['清濁', '調']]:
        key = tuple(group_fields)
        grouped_cache[key] = all_chars_df.groupby(group_fields)

    # 使用缓存的分组
    for ...:
        group_key = tuple(group_fields)
        if group_key in grouped_cache:
            grouped = grouped_cache[group_key]
        else:
            grouped = all_chars_df.groupby(group_fields)
```

**预期提升：30-40%**

### 方案2：向量化处理（中等难度）✅✅

**问题：**
- 逐个处理每个 `(地点, 特征, 特征值)` 组合

**解决方案：**
```python
# 一次性处理所有组合
def analyze_all_combinations_vectorized(all_chars_df, dialect_output, locations, features):
    results = []

    for feature in features:
        # 获取该特征的所有数据
        feature_data = dialect_output[feature]

        # 向量化处理：一次性计算所有地点和特征值
        for loc in locations:
            loc_results = {}

            # 使用 pandas 的向量化操作
            for value, data in feature_data.items():
                loc_chars = data['sub_df'][data['sub_df']['簡稱'] == loc]['漢字'].unique()

                # 向量化分组统计
                char_df_filtered = all_chars_df[all_chars_df['漢字'].isin(loc_chars)]
                grouped = char_df_filtered.groupby(group_fields).size()

                # 批量处理结果
                ...

    return results
```

**预期提升：50-60%**

### 方案3：SQL聚合（最优方案）✅✅✅

**问题：**
- 在Python中做大量的分组和统计

**解决方案：**
```python
# 在SQL中完成分组统计
def analyze_characters_in_sql(char_list, group_fields, char_db_path):
    query = f"""
    SELECT
        {', '.join(group_fields)},
        COUNT(DISTINCT 漢字) as count,
        GROUP_CONCAT(DISTINCT 漢字) as chars
    FROM characters
    WHERE 漢字 IN ({placeholders})
    GROUP BY {', '.join(group_fields)}
    """

    # 一次查询得到所有分组结果
    results = pd.read_sql_query(query, conn, params=char_list)
    return results
```

**预期提升：70-80%**

### 方案4：结果缓存（最简单）✅

**问题：**
- 相同的查询重复计算

**解决方案：**
```python
# 在 pho2sta 函数中添加 Redis 缓存
@cache_result(expire=3600)
def pho2sta(locations, regions, features, status_inputs, ...):
    # 生成缓存键
    cache_key = generate_cache_key(locations, regions, features, status_inputs)

    # 尝试从缓存获取
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    # 执行查询
    results = ...

    # 存入缓存
    redis_client.setex(cache_key, 3600, json.dumps(results))
    return results
```

**预期提升：100%（缓存命中时）**

## 推荐优化顺序

### 阶段1：快速优化（1-2小时）

1. **添加结果缓存**（方案4）
   - 最简单，立即见效
   - 对重复查询提升100%

2. **优化 query_dialect_features**
   - 减少重复的 DataFrame 过滤
   - 预期提升20-30%

### 阶段2：深度优化（1-2天）

3. **向量化处理**（方案2）
   - 重构 analyze_characters 逻辑
   - 预期提升50-60%

4. **SQL聚合**（方案3）
   - 将分组统计移到SQL层
   - 预期提升70-80%

## 性能目标

| 场景 | 当前耗时 | 优化后目标 | 提升 |
|------|---------|-----------|------|
| 小规模 (1地点, 1特征) | 735ms | 200ms | 3.7x |
| 中规模 (2地点, 2特征) | 1,441ms | 400ms | 3.6x |
| 大规模 (5地点, 3特征) | 6,416ms | 1,500ms | 4.3x |

## 总结

### 性能瓶颈

1. **主要瓶颈（75%）**：`analyze_characters_from_cached_df` 被调用268次
2. **次要瓶颈（14%）**：`query_dialect_features` 的数据处理
3. **不是索引问题**：SQL查询只占3%的时间

### 优化策略

1. **短期**：添加结果缓存（最简单，立即见效）
2. **中期**：向量化处理（重构代码，显著提升）
3. **长期**：SQL聚合（最优方案，需要重写逻辑）

### 关键教训

- **瓶颈在应用层，不在数据库层**
- **pandas操作在小数据集上效率低**
- **重复计算是主要问题**
- **缓存是最快的优化方式**
