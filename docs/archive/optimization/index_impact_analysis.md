# dialects 索引影响全面分析

## 问题重新评估

之前的分析**不完整**！删除特征索引会影响多个API。

## 受影响的API清单

### 1. `/compare/ZhongGu` ✅ 优化成功

**查询模式：**
```sql
WHERE 簡稱 IN (...) AND 漢字 IN (...)
GROUP BY 簡稱, 聲母
```

**影响：**
- 使用特征索引：扫描 103,306 行，耗时 43ms
- 使用主索引：扫描 397 行，耗时 4ms
- **已优化：修改代码使用主索引 + Python聚合**

### 2. `/api/phonology_matrix` ❌ 会受负面影响

**查询模式：**
```sql
SELECT 簡稱, 聲母, 韻母, 聲調, 漢字
FROM dialects
WHERE 簡稱 IN (...)
ORDER BY 簡稱, 聲母, 韻母, 聲調
```

**当前性能：**
- 使用 `idx_dialects_features1` 索引
- 扫描 103,306 行
- 耗时 189ms

**删除索引后：**
- 会使用 `idx_dialects_abbr` 索引
- 仍需扫描 103,306 行
- 性能不会改善，可能略微下降

**原因：**
- 这个查询**没有 `漢字 IN (...)` 条件**
- 需要返回所有汉字
- 特征索引对 ORDER BY 有帮助

### 3. `/api/feature_counts` (UNION ALL) ❌ 会受负面影响

**查询模式：**
```sql
SELECT 簡稱, '聲母' as feature_type, 聲母 as value, COUNT(DISTINCT 漢字) AS 字數
FROM dialects
WHERE 簡稱 IN (...)
GROUP BY 簡稱, 聲母
```

**当前性能：**
- 使用 `idx_dialects_features1` 索引
- 耗时 59ms

**删除索引后：**
- 会使用 `idx_dialects_abbr` 索引
- 需要全表扫描后GROUP BY
- **性能会显著下降**

**原因：**
- 这个查询**没有 `漢字 IN (...)` 条件**
- 需要统计所有汉字
- 特征索引是必需的

### 4. `/api/YinWei` (pho2sta) ⚠️ 部分影响

**查询模式：**
```sql
SELECT 簡稱, 漢字, 聲母, 韻母, 聲調, 音節, 多音字
FROM dialects
WHERE 簡稱 IN (...)
```

**当前性能：**
- 使用 `idx_dialects_abbr` 索引
- 扫描 103,306 行
- 耗时 180ms

**删除索引后：**
- 仍使用 `idx_dialects_abbr` 索引
- **无影响**

## 关键发现

### 特征索引的两种使用场景

#### 场景A：有 `漢字 IN (...)` 条件 ❌ 索引有害
```sql
WHERE 簡稱 IN (...) AND 漢字 IN (...)
GROUP BY 簡稱, 聲母
```
- 特征索引导致扫描10万+行
- 主索引只需扫描几百行
- **应该使用主索引**

#### 场景B：无 `漢字 IN (...)` 条件 ✅ 索引有用
```sql
WHERE 簡稱 IN (...)
GROUP BY 簡稱, 聲母
```
- 需要扫描所有汉字
- 特征索引可以优化 GROUP BY
- **应该保留特征索引**

## 正确的优化方案

### ❌ 错误方案：删除特征索引
- 会破坏 `phonology_matrix` 和 `feature_counts` API
- 这些API需要特征索引

### ✅ 正确方案：针对性优化

#### 方案1：保留索引，强制指定（已实施）

**对于 `/compare/ZhongGu`：**
- 修改 `query_by_status_stats_only()` 函数
- 使用主索引 + Python聚合
- **已完成，性能提升10倍**

**对于其他API：**
- 保持现状，继续使用特征索引
- 它们需要这些索引

#### 方案2：创建覆盖索引（可选）

```sql
CREATE INDEX idx_dialects_covering
ON dialects(簡稱, 漢字, 聲母, 韻母, 聲調);
```

**优点：**
- 同时优化两种场景
- 避免回表查询

**缺点：**
- 索引会非常大（可能1GB+）
- 维护成本高

## 最终建议

### ✅ 保留所有现有索引

| 索引 | 用途 | 状态 |
|------|------|------|
| `idx_dialects_char_abbr2` | 主索引，用于有 `漢字 IN (...)` 的查询 | **必需** |
| `idx_dialects_features1/2/3` | 用于无 `漢字 IN (...)` 的GROUP BY查询 | **必需** |
| `idx_dialects_abbr` | 用于只有 `簡稱 IN (...)` 的查询 | **必需** |
| `idx_dialects_poly_full` | 多音字查询 | **必需** |

### ✅ 针对性代码优化

**已优化：**
- `/compare/ZhongGu`：使用主索引 + Python聚合

**无需优化：**
- `/api/phonology_matrix`：需要特征索引
- `/api/feature_counts`：需要特征索引
- `/api/YinWei`：性能可接受

## 性能对比总结

| API | 查询特点 | 最优索引 | 当前状态 |
|-----|---------|---------|---------|
| `/compare/ZhongGu` | `WHERE 簡稱 IN (...) AND 漢字 IN (...)` | `(簡稱, 漢字)` | ✅ 已优化 |
| `/api/phonology_matrix` | `WHERE 簡稱 IN (...)` | `(簡稱, 聲母)` | ✅ 正确 |
| `/api/feature_counts` | `WHERE 簡稱 IN (...) GROUP BY` | `(簡稱, 聲母)` | ✅ 正确 |
| `/api/YinWei` | `WHERE 簡稱 IN (...)` | `(簡稱)` | ✅ 正确 |

## 结论

1. **不应删除特征索引** - 它们对某些API是必需的
2. **已完成的优化是正确的** - `/compare/ZhongGu` 使用主索引
3. **其他API无需修改** - 它们正确使用了特征索引
4. **索引策略是合理的** - 不同查询模式需要不同索引

## 教训

- 索引优化需要考虑所有使用场景
- 不能只看单个API的性能
- 查询模式决定最优索引选择
- 有时需要多个索引来支持不同的查询模式
