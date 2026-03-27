# VillagesML 性能优化 - 索引创建指南

## 概述

为了优化 VillagesML 统计 API 的性能,需要在数据库中添加以下索引。这些索引将显著提升查询速度。

## 需要添加的索引

### 1. ngram_significance 表索引

```sql
-- 索引1: level 字段（用于按级别分组查询）
CREATE INDEX IF NOT EXISTS idx_ngram_significance_level
ON ngram_significance(level);

-- 索引2: p_value 字段（用于筛选显著性 n-gram）
CREATE INDEX IF NOT EXISTS idx_ngram_significance_pvalue
ON ngram_significance(p_value);

-- 索引3: 复合索引 (level, p_value)（用于同时按级别和显著性查询）
CREATE INDEX IF NOT EXISTS idx_ngram_significance_level_pvalue
ON ngram_significance(level, p_value);
```

### 2. 更新统计信息

创建索引后,需要运行 ANALYZE 命令来更新 SQLite 的查询优化器统计信息:

```sql
-- 更新统计信息（生成 sqlite_stat1 表）
ANALYZE;
```

## 执行步骤

1. 连接到 villages.db 数据库
2. 依次执行上述 SQL 语句
3. 验证索引创建成功:

```sql
-- 查看 ngram_significance 表的所有索引
SELECT name, sql
FROM sqlite_master
WHERE type='index' AND tbl_name='ngram_significance';
```

## 预期效果

添加索引后,以下查询的性能将显著提升:

- **按级别分组统计**: 从全表扫描优化为索引扫描
- **显著性筛选**: p_value < 0.05 的查询将使用索引
- **复合查询**: 同时按级别和显著性查询时性能最优

预计性能提升: **3-10倍**（取决于数据量）

## 验证索引效果

执行以下查询来验证索引是否被使用:

```sql
-- 查看查询计划（应该显示 "USING INDEX"）
EXPLAIN QUERY PLAN
SELECT level, COUNT(*) AS total,
       SUM(CASE WHEN p_value < 0.05 THEN 1 ELSE 0 END) AS significant
FROM ngram_significance
GROUP BY level;
```

## 注意事项

1. **索引大小**: 索引会占用额外的磁盘空间（约为表大小的 10-20%）
2. **写入性能**: 索引会略微降低 INSERT/UPDATE 性能,但对于统计查询来说是值得的
3. **维护**: 如果表结构发生变化,可能需要重新创建索引

## 后端已完成的优化

后端已经实现了以下优化（无需数据分析同事操作）:

1. ✅ **API 缓存**: 两个 API 都添加了 5 分钟缓存
2. ✅ **避免 COUNT(*)**: /metadata/stats/tables 使用 sqlite_stat1 估算行数
3. ✅ **查询优化**: /statistics/ngrams 使用 CTE 优化查询

## 联系方式

如有问题,请联系后端开发团队。
