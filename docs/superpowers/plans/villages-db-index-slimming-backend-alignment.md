# villages.db 索引瘦身后端对齐说明

## 背景

服务端和数据处理侧已经确认：当前 `villages.db` 体积主要由索引贡献，N-gram 相关表是最大空间来源。后端侧已检查当前 API 查询形状，并修复了一个不合理的后端依赖：`regional aggregates` 曾经读取原始表 `广东省自然村`，现在已改为读取预处理表 `广东省自然村_预处理`。

后端修复提交：

- `c65acb4 Use preprocessed villages for regional aggregates`

这意味着 VillagesML 的 regional aggregates 不再是保留原始表索引的理由。

但需要注意：原始表 `广东省自然村` 仍可能被通用 SQL/tree 功能依赖，所以原始表索引不纳入本轮清理范围。

## 后端结论

本轮索引瘦身建议聚焦 N-gram 普通单列索引。删除这些索引不会改变接口结果，但可能影响查询性能，因此必须通过副本实验验证。

推荐策略不是裸删所有索引，而是：

1. 保留或新增少量贴合后端查询的复合索引。
2. 删除低价值普通单列索引。
3. 执行 `ANALYZE`。
4. 用 `VACUUM INTO` 生成瘦身库。
5. 对典型 API 做 `EXPLAIN QUERY PLAN` 和耗时基准。

## 推荐保留/生成的复合索引

```sql
CREATE INDEX IF NOT EXISTS idx_ngram_freq_n_position_frequency
ON ngram_frequency(n, position, frequency DESC);

CREATE INDEX IF NOT EXISTS idx_regional_ngram_level_n_region_freq
ON regional_ngram_frequency(level, n, region, frequency DESC);

CREATE INDEX IF NOT EXISTS idx_ngram_tendency_level_region_lift
ON ngram_tendency(level, region, lift DESC);
```

这些索引对应后端当前主要查询：

- `ngram_frequency`: `WHERE n = ? AND position = ? ORDER BY frequency DESC`
- `regional_ngram_frequency`: `WHERE level = ? AND n = ? AND region = ? ORDER BY frequency DESC`
- `ngram_tendency`: `WHERE level = ? AND region = ? ORDER BY lift DESC`

## 建议优先删除的普通单列索引

以下索引可以进入第一轮副本实验：

```text
ngram_tendency:
- idx_ngram_tendency_city
- idx_ngram_tendency_county
- idx_ngram_tendency_township
- idx_ngram_tendency_lift
- idx_ngram_tendency_zscore

regional_ngram_frequency:
- idx_regional_ngram_city
- idx_regional_ngram_county
- idx_regional_ngram_township

ngram_significance:
- idx_ngram_sig_city
- idx_ngram_sig_county
- idx_ngram_sig_township
- idx_ngram_sig_pvalue
```

这些索引通常不是后端 top-k 查询的最佳路径，单列选择性也有限。若复合索引和后端查询形状对齐，删除后风险较低。

## 暂不建议直接删除的索引

以下索引不能在没有替代方案和基准验证前直接删除：

```text
- idx_ngram_tendency_level
- idx_ngram_tendency_level_lift
- idx_regional_ngram_level
- idx_regional_ngram_region
- idx_ngram_sig_level
```

原因：

- `idx_ngram_tendency_level_lift` 仍适合 `WHERE level = 'township' ORDER BY lift DESC LIMIT ?` 这类全局 top tendency 查询。
- `idx_regional_ngram_level` 当前可能仍被 SQLite 用于 `WHERE level = ?` 的过滤。
- `idx_ngram_sig_level` 虽不能解决 `ORDER BY ABS(chi2)` 的排序问题，但仍可能用于 level 过滤。

如果后端明确要求所有 tendency top 查询都带 `region`，那么 `idx_ngram_tendency_level_lift` 才更有把握被 `(level, region, lift DESC)` 替代。否则建议先保留。

## ngram_significance 的特殊问题

当前后端 significance 查询存在这种排序：

```sql
ORDER BY ABS(chi2) DESC
```

普通 `(level, chi2 DESC)` 索引也未必能服务这个排序。因此 `ngram_significance` 不建议简单依靠索引硬扛。

后续更稳妥的方案：

- 数据侧预计算 `abs_chi2` 或 `rank_by_abs_chi2`；
- 或后端确认业务语义后改为 `ORDER BY chi2 DESC`；
- 或在第一轮空间实验中先保留 `idx_ngram_sig_level`，等基准确认后再删除。

## 原始表索引处理口径

`regional aggregates` 的后端错误路径已经修复，不再读取原始表 `广东省自然村`。

但原始表仍可能被通用 SQL/tree 查询能力依赖，因此：

- 本轮不建议删除 `广东省自然村` 的索引；
- 原始表索引清理应作为独立议题，由 SQL/tree 使用情况决定；
- VillagesML 后端不再以 regional aggregates 为理由要求保留原始表索引。

## 建议实验流程

请数据处理侧在副本中执行，不直接操作线上库：

1. 复制当前 `villages.db`。
2. 确认上述复合索引存在。
3. 删除第一批候选普通单列索引。
4. 执行：

```sql
ANALYZE;
```

5. 使用：

```sql
VACUUM INTO 'villages.slim.db';
```

6. 对比：

- 文件大小；
- `dbstat` 表/索引体积；
- 高频 API 的 `EXPLAIN QUERY PLAN`；
- 高频 API 请求耗时。

## 建议覆盖的 API 基准

```text
/api/villages/ngrams/frequency
/api/villages/ngrams/regional
/api/villages/ngrams/tendency
/api/villages/ngrams/significance
/api/villages/metadata/stats/overview
/api/villages/metadata/stats/regions
/api/villages/regional/aggregates/city
/api/villages/regional/aggregates/county
/api/villages/regional/aggregates/town
/api/villages/regional/vectors
```

## 给数据处理同事的简短结论

后端认可 N-gram 普通单列索引瘦身方向，但不建议承诺“完全不影响性能”。准确表述应为：

> 删除候选普通索引不影响接口结果；性能风险需要通过少量复合索引替代、`ANALYZE`、以及 API 基准验证来控制。原始表 `广东省自然村` 的索引本轮不删，因为 SQL/tree 仍可能依赖；VillagesML regional aggregates 已修复为读取预处理表，不再依赖原始表。
