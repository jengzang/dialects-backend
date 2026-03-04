# API 统计数据写入机制详解

## 🔍 问题发现

在实现过程中发现：**`update_count()` 函数定义了但没有被调用**，导致新增的统计表无法接收数据。

## ✅ 已修复

在 `app/logs/service/api_limit_keyword.py` 的 `ApiLoggingMiddleware` 中添加了 `update_count(path)` 调用。

---

## 📊 完整的数据流

### 1. 请求捕获

```
用户请求 API
    ↓
FastAPI 应用
    ↓
中间件栈（按顺序执行）
    ├─ CORSMiddleware
    ├─ GZipMiddleware
    ├─ TrafficLoggingMiddleware  ← 记录详细日志（auth.db）
    └─ ApiLoggingMiddleware      ← 记录参数 + 统计（logs.db）✨
```

### 2. ApiLoggingMiddleware 的工作流程

```python
async def dispatch(self, request: Request, call_next):
    path = request.url.path

    # 1. 检查是否需要记录
    if should_skip_route(path):
        return await call_next(request)

    # 2. 记录参数（可选，根据配置）
    if config.get("log_params") or config.get("log_body"):
        log_all_fields(path, params_to_log)  # → keyword_log_queue

    # 3. 更新统计（每个请求都会执行）✨
    update_count(path)  # → statistics_queue

    # 4. 继续处理请求
    response = await call_next(request)
    return response
```

### 3. 数据入队

```python
# app/logs/service/api_logger.py 第 260-263 行
def update_count(path: str):
    """更新 API 调用次数统计"""
    today = datetime.now()
    statistics_queue.put((path, today))  # 放入队列
```

**入队数据格式**：
```python
(path, datetime_obj)
# 例如：('/api/YinWei', datetime(2026, 3, 4, 10, 30, 15))
```

### 4. 后台线程批量写入

```python
# app/logs/service/api_logger.py 第 119-148 行
def statistics_writer():
    """后台线程：批量更新 ApiStatistics"""
    batch = []
    batch_size = 50        # 批量大小
    batch_timeout = 120.0  # 超时时间（秒）

    while True:
        try:
            # 从队列获取数据（最多等待 120 秒）
            item = statistics_queue.get(timeout=batch_timeout)
            batch.append(item)

            # 条件 1：批次满了（50 条）
            if len(batch) >= batch_size:
                _process_statistics_batch(batch)
                batch = []

        except Empty:
            # 条件 2：超时了（120 秒）
            if batch:
                _process_statistics_batch(batch)
                batch = []
```

### 5. 批量处理逻辑

```python
# app/logs/service/api_logger.py 第 151-214 行
def _process_statistics_batch(batch: list):
    """批量处理统计更新"""
    db = LogsSessionLocal()
    try:
        for path, date_obj in batch:
            # 1. 更新 api_statistics 表（现有）
            update_statistic(db, "usage_total", None, "path", path)
            update_statistic(db, "usage_daily", date_obj, "path", path)

            # 2. 更新 api_usage_hourly 表（新增）✨
            current_hour = datetime.now().replace(minute=0, second=0, microsecond=0)
            result = db.execute(
                "UPDATE api_usage_hourly SET total_calls = total_calls + 1 WHERE hour = :hour",
                {"hour": current_hour}
            )
            if result.rowcount == 0:
                db.execute(
                    "INSERT OR IGNORE INTO api_usage_hourly (hour, total_calls) VALUES (:hour, 1)",
                    {"hour": current_hour}
                )

            # 3. 更新 api_usage_daily 表（新增）✨
            current_date = datetime.now().date()
            result = db.execute(
                "UPDATE api_usage_daily SET call_count = call_count + 1 WHERE date = :date AND path = :path",
                {"date": current_date, "path": path}
            )
            if result.rowcount == 0:
                db.execute(
                    "INSERT OR IGNORE INTO api_usage_daily (date, path, call_count) VALUES (:date, :path, 1)",
                    {"date": current_date, "path": path}
                )

        db.commit()  # 一次性提交所有更新
    except Exception as e:
        print(f"[X] 统计批次失败: {e}")
        db.rollback()
    finally:
        db.close()
```

---

## ⏱️ 写入时机详解

### 触发条件（满足任一即写入）

| 条件 | 阈值 | 说明 |
|------|------|------|
| **批量大小** | 50 条 | 队列中累积了 50 个 API 调用 |
| **超时时间** | 120 秒 | 距离上次写入已过 2 分钟 |

### 实际场景分析

**场景 1：高流量时段**
```
假设每秒 10 个请求：
- 5 秒后累积 50 条 → 触发写入
- 数据延迟：< 5 秒
```

**场景 2：低流量时段**
```
假设每分钟 5 个请求：
- 10 分钟累积 50 条 → 触发写入
- 或者 2 分钟超时 → 触发写入（即使只有 10 条）
- 数据延迟：最多 2 分钟
```

**场景 3：极低流量**
```
假设 1 小时只有 3 个请求：
- 第 1 个请求：入队
- 2 分钟后：超时写入（1 条）
- 第 2 个请求：入队
- 2 分钟后：超时写入（1 条）
- ...
- 数据延迟：最多 2 分钟
```

---

## 🔧 队列配置详解

### 队列定义

```python
# app/logs/service/api_logger.py 第 33 行
statistics_queue = multiprocessing.Queue(maxsize=1000)
```

**参数说明**：
- **类型**：`multiprocessing.Queue`
  - 支持多进程（Gunicorn 多 worker 模式）
  - 线程安全 + 进程安全
- **容量**：1000 条
  - 理论上可以缓冲 1000 个待处理的 API 调用
  - 实际上很少会满（因为每 50 条或 120 秒就会写入）

### 队列满时的行为

```python
# 如果队列满了（1000 条），put() 会阻塞
statistics_queue.put((path, today))  # 阻塞直到有空位

# 实际上不会发生，因为：
# - 每 50 条就写入一次
# - 队列容量是 1000 条
# - 需要 20 次批量写入才会满
```

### 队列性能

```
入队操作：O(1)，几乎无延迟
出队操作：O(1)，批量处理
内存占用：每条约 100 字节，1000 条 ≈ 100KB
```

---

## 📈 数据一致性保证

### 1. UPSERT 模式

```sql
-- 先尝试更新
UPDATE api_usage_hourly
SET total_calls = total_calls + 1
WHERE hour = '2026-03-04 10:00:00';

-- 如果没有更新任何行（记录不存在），则插入
IF rowcount == 0:
    INSERT OR IGNORE INTO api_usage_hourly (hour, total_calls)
    VALUES ('2026-03-04 10:00:00', 1);
```

**优势**：
- ✅ 避免并发冲突
- ✅ 自动处理首次插入
- ✅ 原子性操作

### 2. 事务保证

```python
db = LogsSessionLocal()
try:
    # 批量处理 50 条记录
    for path, date_obj in batch:
        # ... 更新操作

    db.commit()  # 一次性提交
except Exception as e:
    db.rollback()  # 失败则回滚
finally:
    db.close()
```

**优势**：
- ✅ 要么全部成功，要么全部失败
- ✅ 不会出现部分数据丢失

### 3. 队列持久化

**注意**：`multiprocessing.Queue` 是内存队列，**不持久化**。

**影响**：
- ❌ 如果服务器突然崩溃，队列中的数据会丢失
- ✅ 但最多丢失 50 条记录（< 2 分钟的数据）
- ✅ 对于统计数据来说，这个损失是可接受的

**如果需要更高的可靠性**：
- 可以使用 Redis 队列（持久化）
- 或者减小批量大小和超时时间

---

## 🧪 验证数据写入

### 1. 启动服务器

```bash
uvicorn app.main:app --reload --port 5000
```

### 2. 发送测试请求

```bash
# 发送 10 个请求
for i in {1..10}; do
  curl "http://localhost:5000/api/YinWei?locations=广州"
  sleep 0.5
done
```

### 3. 等待写入

```bash
# 等待 2 分钟（超时时间）
sleep 120
```

### 4. 检查数据

```bash
sqlite3 data/logs.db "
SELECT hour, total_calls, updated_at
FROM api_usage_hourly
ORDER BY hour DESC
LIMIT 5;
"

sqlite3 data/logs.db "
SELECT date, path, call_count, updated_at
FROM api_usage_daily
WHERE date = date('now')
ORDER BY call_count DESC
LIMIT 10;
"
```

---

## 📊 监控建议

### 1. 队列长度监控

```python
# 添加监控端点
@router.get("/admin/queue-status")
async def get_queue_status():
    return {
        "statistics_queue": {
            "size": statistics_queue.qsize(),
            "maxsize": statistics_queue._maxsize,
            "usage": f"{statistics_queue.qsize() / statistics_queue._maxsize * 100:.1f}%"
        }
    }
```

### 2. 写入延迟监控

```python
# 在 _process_statistics_batch 中添加
import time

start_time = time.time()
_process_statistics_batch(batch)
duration = time.time() - start_time

if duration > 5:  # 写入超过 5 秒
    print(f"[WARN] 批量写入耗时过长: {duration:.2f}s")
```

### 3. 数据完整性检查

```sql
-- 检查是否有缺失的小时
SELECT
    datetime('now', '-24 hours', 'start of hour') as expected_start,
    COUNT(*) as actual_count,
    24 as expected_count
FROM api_usage_hourly
WHERE hour >= datetime('now', '-24 hours', 'start of hour');

-- 如果 actual_count < expected_count，说明有数据缺失
```

---

## 🚀 性能优化建议

### 1. 调整批量大小

```python
# 高流量场景：减小批量大小，降低延迟
batch_size = 20  # 原来 50

# 低流量场景：增大批量大小，减少数据库连接
batch_size = 100  # 原来 50
```

### 2. 调整超时时间

```python
# 实时性要求高：减小超时时间
batch_timeout = 30.0  # 原来 120.0

# 实时性要求低：增大超时时间
batch_timeout = 300.0  # 原来 120.0
```

### 3. 使用连接池

```python
# 当前实现每次批量写入都创建新连接
db = LogsSessionLocal()

# 优化：使用连接池（已在其他地方实现）
from app.sql.db_pool import get_db_pool
pool = get_db_pool(LOGS_DATABASE_PATH)
with pool.get_connection() as conn:
    # 批量写入
```

---

## 📝 总结

### 数据写入流程

```
API 请求
  ↓ (实时)
ApiLoggingMiddleware.dispatch()
  ↓ (实时)
update_count(path)
  ↓ (实时)
statistics_queue.put((path, today))
  ↓ (异步，非阻塞)
statistics_writer() 后台线程
  ↓ (批量，50 条或 120 秒)
_process_statistics_batch(batch)
  ↓ (事务)
写入 3 张表：
  - api_statistics (现有)
  - api_usage_hourly (新增)
  - api_usage_daily (新增)
```

### 关键参数

| 参数 | 值 | 说明 |
|------|-----|------|
| 队列容量 | 1000 条 | 最多缓冲 1000 个待处理请求 |
| 批量大小 | 50 条 | 每 50 条写入一次 |
| 超时时间 | 120 秒 | 最多等待 2 分钟 |
| 数据延迟 | 0-120 秒 | 取决于流量大小 |
| 数据丢失风险 | < 50 条 | 服务器崩溃时最多丢失 |

### 修复内容

✅ 在 `ApiLoggingMiddleware` 中添加了 `update_count(path)` 调用
✅ 现在每个 API 请求都会触发统计更新
✅ 数据会在 50 条或 120 秒后写入数据库

---

**更新时间**：2026-03-04
**修复人员**：后端团队
