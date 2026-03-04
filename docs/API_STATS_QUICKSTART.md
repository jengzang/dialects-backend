# API 调用统计表 - 快速开始

## 新增功能

在 `logs.db` 中新增了两张表，用于永久记录 API 调用统计：

1. **api_usage_hourly** - 小时级总调用统计（不区分API）
2. **api_usage_daily** - 每日每API调用统计

## 新增 API 接口

所有接口均为公开访问，无需认证：

```bash
# 1. 小时级趋势（最近24小时）
GET /logs/stats/hourly?hours=24

# 2. 每日趋势（最近30天）
GET /logs/stats/daily?days=30

# 3. 每日趋势（指定API）
GET /logs/stats/daily?days=30&path=/api/YinWei

# 4. API 排行榜（今天前10名）
GET /logs/stats/ranking?limit=10

# 5. API 历史趋势（最近30天）
GET /logs/stats/api-history?path=/api/YinWei&days=30
```

## 快速测试

```bash
# 1. 启动服务器
uvicorn app.main:app --reload --port 5000

# 2. 运行测试脚本
python test_stats_api.py

# 3. 或手动测试
curl "http://localhost:5000/logs/stats/hourly?hours=24"
```

## 数据验证

```bash
# 查看表结构
sqlite3 data/logs.db "PRAGMA table_info(api_usage_hourly)"
sqlite3 data/logs.db "PRAGMA table_info(api_usage_daily)"

# 查看数据
sqlite3 data/logs.db "SELECT * FROM api_usage_hourly ORDER BY hour DESC LIMIT 5"
sqlite3 data/logs.db "SELECT * FROM api_usage_daily WHERE date = date('now') ORDER BY call_count DESC LIMIT 10"
```

## 实现细节

详见：[docs/api_stats_implementation.md](docs/api_stats_implementation.md)

## 关键文件

- `app/logs/migrations/add_hourly_daily_stats.py` - 数据库迁移
- `app/logs/service/api_logger.py` - 数据写入逻辑
- `app/routes/stats.py` - API 接口
- `test_stats_api.py` - 测试脚本
