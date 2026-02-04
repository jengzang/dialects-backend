# 日志统计系统使用文档

## 概述

本系统提供完整的日志统计和分析功能，包括：
- ✅ API 调用统计
- ✅ 关键词使用分析
- ✅ 定时清理和聚合
- ✅ 管理员后台管理

---

## API 端点

### 1. 查询类 API（公开或需登录）

#### 1.1 获取 Top 关键词
```http
GET /api/logs/keyword/top
```

**参数：**
- `field` (可选): 筛选特定字段，如 `locations`、`regions`
- `date` (可选): 日期筛选 `YYYY-MM-DD`，不填则返回总计
- `limit` (默认20): 返回前 N 个关键词

**示例：**
```bash
# 获取所有字段的总计 Top 20
curl http://localhost:5000/api/logs/keyword/top

# 获取 locations 字段的总计 Top 10
curl "http://localhost:5000/api/logs/keyword/top?field=locations&limit=10"

# 获取 2025-01-21 的所有字段 Top 20
curl "http://localhost:5000/api/logs/keyword/top?date=2025-01-21"
```

**响应：**
```json
{
  "stat_type": "keyword_total",
  "date": null,
  "field_filter": "locations",
  "total_items": 10,
  "data": [
    {
      "field": "locations",
      "keyword": "广州",
      "count": 1523
    }
  ]
}
```

---

#### 1.2 获取 API 调用统计
```http
GET /api/logs/api/usage
```

**参数：**
- `date` (可选): 日期筛选 `YYYY-MM-DD`
- `limit` (默认20): 返回前 N 个 API

**示例：**
```bash
# 总计 Top 20
curl http://localhost:5000/api/logs/api/usage

# 2025-01-21 的统计
curl "http://localhost:5000/api/logs/api/usage?date=2025-01-21"
```

**响应：**
```json
{
  "stat_type": "usage_total",
  "date": null,
  "total_api_calls": 50234,
  "total_endpoints": 15,
  "data": [
    {
      "path": "/api/phonology",
      "count": 25120,
      "percentage": 50.0
    }
  ]
}
```

---

#### 1.3 搜索关键词日志
```http
GET /api/logs/keyword/search
```

**参数：**
- `field` (可选): 字段名
- `value` (可选): 关键词值（模糊匹配）
- `path` (可选): API 路径（模糊匹配）
- `start_date` (可选): 开始日期 `YYYY-MM-DD`
- `end_date` (可选): 结束日期 `YYYY-MM-DD`
- `limit` (默认100): 返回数量
- `offset` (默认0): 分页偏移

**示例：**
```bash
# 搜索 locations 字段中包含"广州"的记录
curl "http://localhost:5000/api/logs/keyword/search?field=locations&value=广州"

# 搜索 /api/phonology 的所有调用（最近）
curl "http://localhost:5000/api/logs/keyword/search?path=/api/phonology&start_date=2025-01-20"
```

---

#### 1.4 获取统计概览
```http
GET /api/logs/stats/summary
```

**参数：**
- `days` (默认7): 统计最近 N 天

**响应：**
```json
{
  "overview": {
    "total_logs": 150234,
    "recent_logs": 15234,
    "days": 7
  },
  "daily_trend": [
    {"date": "2025-01-21", "count": 2345}
  ],
  "top_apis": [
    {"path": "/api/phonology", "count": 25120}
  ],
  "top_keywords": [
    {"field": "locations", "keyword": "广州", "count": 1523}
  ]
}
```

---

#### 1.5 获取字段统计分布
```http
GET /api/logs/stats/fields
```

**参数：**
- `date` (可选): 日期筛选

**响应：**
```json
{
  "date": null,
  "data": [
    {
      "field": "locations",
      "unique_keywords": 523,
      "total_calls": 15234
    }
  ]
}
```

---

### 2. 管理类 API（需要管理员权限）

#### 2.1 清理旧日志
```http
DELETE /api/logs/cleanup
```

**参数：**
- `days` (默认30): 删除 N 天前的日志
- `dry_run` (默认false): 试运行，不实际删除

**示例：**
```bash
# 试运行：查看会删除多少数据
curl -X DELETE "http://localhost:5000/api/logs/cleanup?days=30&dry_run=true" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"

# 实际删除 30 天前的日志
curl -X DELETE "http://localhost:5000/api/logs/cleanup?days=30" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

---

#### 2.2 手动触发统计聚合
```http
POST /api/logs/aggregate
```

**示例：**
```bash
curl -X POST "http://localhost:5000/api/logs/aggregate" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

---

#### 2.3 获取数据库大小信息
```http
GET /api/logs/database/size
```

**响应：**
```json
{
  "database_path": "/path/to/logs.db",
  "file_size_bytes": 52428800,
  "file_size_mb": 50.0,
  "tables": {
    "api_keyword_log": 150234,
    "api_statistics": 5234
  },
  "statistics_breakdown": {
    "keyword_total": 2345,
    "keyword_daily": 1523,
    "usage_total": 856,
    "usage_daily": 510
  }
}
```

---

## 定时任务

### 自动执行的任务

1. **清理旧日志**
   - 时间：每周日凌晨 3:00
   - 操作：删除 30 天前的关键词日志和每日统计
   - 保留：总计统计永久保留

2. **聚合关键词统计**
   - 时间：每小时第 5 分钟
   - 操作：重新聚合关键词统计
   - 范围：最近 7 天的每日统计 + 总计统计

### 手动执行任务

```bash
# 立即执行清理任务
python -m app.logs.scheduler cleanup

# 立即执行聚合任务
python -m app.logs.scheduler aggregate
```

---

## 数据结构

### api_keyword_log 表
存储每次 API 调用的参数记录。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| timestamp | DATETIME | 时间戳 |
| path | VARCHAR(255) | API 路径 |
| field | VARCHAR(100) | 参数字段名 |
| value | TEXT | 参数值 |

### api_statistics 表
存储聚合后的统计数据。

| 字段 | 类型 | 说明 |
|------|------|------|
| stat_type | VARCHAR(50) | keyword_total/keyword_daily/usage_total/usage_daily |
| date | DATETIME | NULL=总计，非NULL=每日统计 |
| category | VARCHAR(100) | 分类（path/field） |
| item | VARCHAR(255) | 具体项 |
| count | INTEGER | 计数 |

---

## 依赖安装

需要安装 APScheduler：

```bash
pip install apscheduler
```

---

## 常见问题

### Q1: 统计数据不准确怎么办？
**A:** 手动触发聚合：
```bash
curl -X POST "http://localhost:5000/api/logs/aggregate" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

### Q2: 数据库文件太大怎么办？
**A:** 手动清理旧数据：
```bash
# 先试运行查看影响
curl -X DELETE "http://localhost:5000/api/logs/cleanup?days=15&dry_run=true" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"

# 实际删除
curl -X DELETE "http://localhost:5000/api/logs/cleanup?days=15" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

### Q3: 如何查看定时任务是否正常运行？
**A:** 查看日志输出，启动时会显示：
```
✅ 定时任务调度器已启动
   - 清理旧日志: 每周日 03:00
   - 聚合统计: 每小时第 5 分钟
```

---

## 性能优化建议

1. **索引优化**
   - 所有关键字段已添加索引
   - timestamp, path, field 都有单独或联合索引

2. **定期清理**
   - 建议保留 30-60 天的详细日志
   - 总计统计永久保留

3. **批量写入**
   - 关键词日志使用批量写入（50条/批）
   - 减少数据库 I/O 压力

4. **SQLite 优化**
   - 已启用 WAL 模式
   - 设置 64MB 缓存
   - 使用 NORMAL 同步模式

---

## 监控和告警（建议）

可以通过 `/api/logs/database/size` 监控数据库大小：

```bash
# 定期检查（如每天一次）
curl "http://localhost:5000/api/logs/database/size" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"

# 如果文件大小超过 500MB，考虑清理
```

---

## 备份策略

```bash
# 备份 logs.db
cp data/logs.db data/logs.db.backup.$(date +%Y%m%d)

# 恢复
cp data/logs.db.backup.20250121 data/logs.db
```
