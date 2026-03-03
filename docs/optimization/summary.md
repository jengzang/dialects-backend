# VillagesML API 性能优化总结

## 优化内容

### 1. 后端优化（已完成）

#### 1.1 创建缓存工具模块
- **文件**: `app/tools/VillagesML/cache_utils.py`
- **功能**:
  - 通用的 API 缓存装饰器 `@api_cache`
  - 基于 Redis 的缓存机制
  - 支持自定义 TTL 和缓存键前缀
  - 自动序列化/反序列化 JSON 数据

#### 1.2 优化 `/api/villages/metadata/stats/tables`
- **文件**: `app/tools/VillagesML/metadata/stats.py`
- **优化点**:
  - ✅ 添加 5 分钟缓存 (`@api_cache(ttl=300)`)
  - ✅ 使用 `sqlite_stat1` 表获取行数估算,避免 COUNT(*) 全表扫描
  - ✅ 仅在 `sqlite_stat1` 不可用时才使用 COUNT(*) 作为 fallback
- **预期效果**: 首次请求后,后续请求响应时间从 5-10 秒降至 < 100ms

#### 1.3 优化 `/api/villages/statistics/ngrams`
- **文件**: `app/tools/VillagesML/statistics/__init__.py`
- **优化点**:
  - ✅ 添加 5 分钟缓存 (`@api_cache(ttl=300)`)
  - ✅ 将同步函数改为异步,使用 `run_in_threadpool` 执行数据库操作
  - ✅ 保留原有的 CTE 查询优化
- **预期效果**: 首次请求后,后续请求响应时间从 3-5 秒降至 < 100ms

### 2. 数据库索引（需要数据分析同事添加）

#### 2.1 索引创建 SQL
```sql
-- 索引1: level 字段
CREATE INDEX IF NOT EXISTS idx_ngram_significance_level
ON ngram_significance(level);

-- 索引2: p_value 字段
CREATE INDEX IF NOT EXISTS idx_ngram_significance_pvalue
ON ngram_significance(p_value);

-- 索引3: 复合索引 (level, p_value)
CREATE INDEX IF NOT EXISTS idx_ngram_significance_level_pvalue
ON ngram_significance(level, p_value);

-- 更新统计信息
ANALYZE;
```

#### 2.2 索引说明文档
- **文件**: `docs/performance_optimization_indexes.md`
- **内容**: 详细的索引创建指南,包括执行步骤、预期效果、验证方法

### 3. 性能测试脚本

- **文件**: `test_performance_optimization.py`
- **功能**:
  - 测试两个 API 的性能
  - 对比缓存命中前后的响应时间
  - 计算性能提升倍数

## 使用方法

### 启动服务器
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 5000
```

### 运行性能测试
```bash
python test_performance_optimization.py
```

## 预期性能提升

### 缓存效果
- **首次请求**: 保持原有速度（需要查询数据库）
- **缓存命中**: 响应时间 < 100ms
- **性能提升**: 30-100x（取决于原始查询复杂度）

### 索引效果（添加索引后）
- **首次请求**: 3-10x 性能提升
- **缓存命中**: 无影响（已经很快）
- **综合效果**: 首次请求也能在 1-2 秒内完成

## 注意事项

1. **缓存失效**: 缓存 TTL 为 5 分钟,数据更新后最多 5 分钟才能看到新数据
2. **Redis 依赖**: 在 WEB 模式下需要 Redis,MINE/EXE 模式下缓存不生效
3. **索引维护**: 添加索引后,INSERT/UPDATE 性能会略微下降,但对统计查询是值得的

## 文件清单

### 新增文件
- `app/tools/VillagesML/cache_utils.py` - 缓存工具模块
- `docs/performance_optimization_indexes.md` - 索引创建指南
- `test_performance_optimization.py` - 性能测试脚本

### 修改文件
- `app/tools/VillagesML/metadata/stats.py` - 添加缓存和查询优化
- `app/tools/VillagesML/statistics/__init__.py` - 添加缓存和异步支持

## 下一步

1. ✅ 后端优化已完成
2. ⏳ 等待数据分析同事添加索引
3. ⏳ 运行性能测试验证效果
4. ⏳ 监控生产环境性能指标
