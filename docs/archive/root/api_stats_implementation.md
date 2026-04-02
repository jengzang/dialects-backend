# API 调用统计表实现文档

## 概述

本文档记录了在 `logs.db` 中新增的两张 API 调用统计表的实现细节。

## 数据库表结构

### 1. api_usage_hourly - 小时级总调用统计

记录所有 API 的总调用次数，每小时一条记录。

```sql
CREATE TABLE api_usage_hourly (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hour DATETIME NOT NULL,           -- 格式: '2026-03-04 15:00:00'
    total_calls INTEGER DEFAULT 0,    -- 该小时内所有API的总调用次数
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX idx_hourly_hour ON api_usage_hourly(hour);
```

**特点**：
- 不区分具体 API 路径
- 每小时只有一条记录
- 永久保留，不自动清理

### 2. api_usage_daily - 每日每API调用统计

记录每个 API 每天的调用次数。

```sql
CREATE TABLE api_usage_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL,               -- 格式: '2026-03-04'
    path VARCHAR(255) NOT NULL,       -- API路径，如 '/api/YinWei'
    call_count INTEGER DEFAULT 0,     -- 该API当天的调用次数
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX idx_daily_date_path ON api_usage_daily(date, path);
CREATE INDEX idx_daily_date ON api_usage_daily(date);
CREATE INDEX idx_daily_path ON api_usage_daily(path);
```

**特点**：
- 区分 API 路径
- 每天每个 API 一条记录
- 永久保留，不自动清理

## 实现架构

### 数据写入流程

```
API 请求
  ↓
TrafficLoggingMiddleware (中间件)
  ↓
update_count(path) → statistics_queue
  ↓
statistics_writer() (后台线程)
  ↓
_process_statistics_batch()
  ↓
写入 3 张表:
  - api_statistics (现有)
  - api_usage_hourly (新增)
  - api_usage_daily (新增)
```

### 关键文件

**1. 数据库迁移**
- `app/logs/migrations/add_hourly_daily_stats.py`
  - 创建两张新表
  - 创建索引
  - 幂等性设计（可重复执行）

**2. 数据写入**
- `app/logs/service/api_logger.py`
  - 修改 `_process_statistics_batch()` 函数
  - 使用 UPSERT 模式（UPDATE + INSERT）
  - 批量写入（50条/批，120秒超时）

**3. 数据读取**
- `app/routes/stats.py`
  - 4 个公开 API 端点
  - 无需认证
  - 支持时间范围查询

**4. 应用启动**
- `app/main.py`
  - 在 `lifespan()` 中调用迁移
  - 启动时自动创建表

## API 接口

### 1. GET /logs/stats/hourly

获取小时级调用趋势

**参数**：
- `hours` (int, optional): 最近N小时，默认24，最多168（7天）

**响应示例**：
```json
{
  "period": "24h",
  "data": [
    {
      "hour": "2026-03-04 15:00:00",
      "total_calls": 1250
    }
  ],
  "summary": {
    "total_calls": 28500,
    "avg_calls_per_hour": 1187,
    "peak_hour": "2026-03-04 16:00:00",
    "peak_calls": 1380
  }
}
```

### 2. GET /logs/stats/daily

获取每日调用趋势

**参数**：
- `days` (int, optional): 最近N天，默认30，最多365
- `path` (str, optional): 指定API路径

**响应示例**：
```json
{
  "period": "30d",
  "path": null,
  "data": [
    {
      "date": "2026-03-04",
      "total_calls": 28500
    }
  ],
  "summary": {
    "total_calls": 850000,
    "avg_calls_per_day": 28333,
    "peak_date": "2026-03-05",
    "peak_calls": 30200
  }
}
```

### 3. GET /logs/stats/ranking

获取 API 排行榜

**参数**：
- `date` (str, optional): 指定日期（YYYY-MM-DD），默认今天
- `limit` (int, optional): 返回前N个，默认10，最多100

**响应示例**：
```json
{
  "date": "2026-03-04",
  "ranking": [
    {
      "rank": 1,
      "path": "/api/YinWei",
      "call_count": 5200,
      "percentage": 18.2
    }
  ],
  "total_calls": 28500
}
```

### 4. GET /logs/stats/api-history

获取指定 API 的历史趋势

**参数**：
- `path` (str, required): API路径
- `days` (int, optional): 最近N天，默认30，最多365

**响应示例**：
```json
{
  "path": "/api/YinWei",
  "period": "30d",
  "data": [
    {
      "date": "2026-03-04",
      "call_count": 5200
    }
  ],
  "summary": {
    "total_calls": 156000,
    "avg_calls_per_day": 5200,
    "peak_date": "2026-03-05",
    "peak_calls": 5500
  }
}
```

## 测试验证

### 1. 数据库表验证

```bash
sqlite3 data/logs.db "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'api_usage_%'"
```

应该看到：
- api_usage_hourly
- api_usage_daily

### 2. 数据写入验证

```bash
# 启动服务器
uvicorn app.main:app --reload --port 5000

# 调用几个 API
curl http://localhost:5000/api/YinWei

# 等待 120 秒（批量写入超时）

# 检查数据
sqlite3 data/logs.db "SELECT * FROM api_usage_hourly ORDER BY hour DESC LIMIT 5"
sqlite3 data/logs.db "SELECT * FROM api_usage_daily WHERE date = date('now') ORDER BY call_count DESC LIMIT 10"
```

### 3. API 接口验证

```bash
# 使用测试脚本
python test_stats_api.py

# 或手动测试
curl "http://localhost:5000/logs/stats/hourly?hours=24"
curl "http://localhost:5000/logs/stats/daily?days=7"
curl "http://localhost:5000/logs/stats/ranking?limit=10"
curl "http://localhost:5000/logs/stats/api-history?path=/api/YinWei&days=30"
```

## 性能考虑

### 写入性能
- ✅ 复用现有 `statistics_queue`，无额外队列开销
- ✅ 批量写入（50条/批，120秒超时）
- ✅ UPSERT 模式避免并发冲突
- ✅ 异步写入，不阻塞请求处理

### 查询性能
- ✅ 创建必要的索引：
  - `idx_hourly_hour` - 小时查询
  - `idx_daily_date_path` - 日期+路径联合查询
  - `idx_daily_date` - 日期范围查询
  - `idx_daily_path` - 路径查询
- ✅ 限制查询范围（最多7天/365天）
- ✅ 使用聚合查询减少数据传输

### 存储空间
- 小时表：每小时1条 × 24小时 × 365天 = 8,760条/年 ≈ 1MB/年
- 每日表：假设100个API × 365天 = 36,500条/年 ≈ 5MB/年
- 总计：约 6MB/年（可忽略不计）

## 注意事项

### 1. 数据一致性
- 使用 UNIQUE 索引防止重复记录
- 使用 UPSERT 模式处理并发写入
- 使用事务保证原子性

### 2. 时区处理
- 使用 `datetime.now()` 获取服务器本地时间
- 小时字段精确到小时（分钟和秒为00）
- 日期字段使用 DATE 类型（YYYY-MM-DD）

### 3. 数据保留
- 永久保留，不自动清理
- 如需清理，可手动执行 SQL：
  ```sql
  DELETE FROM api_usage_hourly WHERE hour < date('now', '-1 year');
  DELETE FROM api_usage_daily WHERE date < date('now', '-1 year');
  ```

### 4. 多进程兼容性
- 使用 `multiprocessing.Queue` 支持多进程
- 批量写入减少数据库锁竞争
- UPSERT 模式避免并发冲突

## 未来扩展

### 可能的优化方向

1. **数据聚合**
   - 添加周级、月级统计表
   - 定时任务聚合历史数据

2. **缓存优化**
   - Redis 缓存热门查询
   - 1小时 TTL

3. **可视化**
   - 前端图表展示
   - 实时监控面板

4. **告警功能**
   - 调用量异常检测
   - 邮件/Webhook 通知

## 相关文档

- [CLAUDE.md](../CLAUDE.md) - 项目架构文档
- [API 日志系统](../docs/api_logging_system.md) - 日志系统设计
- [数据库设计](../docs/database_design.md) - 数据库架构

## 更新日志

- 2026-03-04: 初始实现
  - 创建两张统计表
  - 实现数据写入逻辑
  - 添加 4 个查询 API
  - 编写测试脚本
