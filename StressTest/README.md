# FastAPI 压力测试工具包

这个工具包帮助您对 FastAPI 方言数据库应用进行全面的压力测试和性能分析。

## 📦 安装依赖

```bash
pip install locust psutil
```

## 🚀 快速开始

### 1. 配置测试参数

编辑 `config.py` 文件：

```python
# 修改服务器地址
BASE_URL = "http://localhost:5000"  # 本地测试

# 配置测试用户（需要先在系统中创建）
TEST_USERS = [
    {"username": "testuser1", "password": "Test123456"},
    {"username": "testuser2", "password": "Test123456"},
]
```

### 2. 创建测试用户

在运行压测前，需要先创建测试用户：

```bash
# 方法 1: 通过 API 注册
curl -X POST http://localhost:5000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser1", "password": "Test123456", "email": "test1@example.com"}'

# 方法 2: 直接在数据库中创建（如果有管理权限）
```

### 3. 运行压力测试

#### 方式 A: Web UI 模式（推荐）

```bash
# 启动 Locust Web UI
locust -f locustfile.py --host http://localhost:5000

# 然后在浏览器打开: http://localhost:8089
# 设置并发用户数和启动速率，点击 "Start swarming"
```

#### 方式 B: 无头模式（命令行）

```bash
# 50 个并发用户，每秒启动 5 个，运行 5 分钟
locust -f locustfile.py --host http://localhost:5000 \
  --headless -u 50 -r 5 -t 5m

# 100 个并发用户，运行 10 分钟
locust -f locustfile.py --host http://localhost:5000 \
  --headless -u 100 -r 10 -t 10m
```

### 4. 同时运行性能监控

在另一个终端窗口运行监控脚本：

```bash
# 自动查找 uvicorn 进程
python monitor.py --auto

# 或手动指定进程 ID
python monitor.py --pid 12345

# 监控 5 分钟后自动停止
python monitor.py --auto --duration 300
```

## 📊 测试场景说明

### 用户类型

1. **DialectAPIUser (60%)** - 已登录的普通用户
   - 搜索字符 (40%)
   - 音韵分析 (20%)
   - 获取地点 (15%)
   - 获取坐标 (10%)
   - 获取区域 (10%)
   - 自定义查询 (5%)

2. **AnonymousUser (30%)** - 匿名用户
   - 搜索字符 (50%)
   - 获取地点 (30%)
   - 访问首页 (20%)

3. **AdminUser (10%)** - 管理员用户
   - 查看 API 使用统计 (40%)
   - 查看用户列表 (30%)
   - 查看登录日志 (20%)
   - 查看用户统计 (10%)

### 测试的端点

- `/api/search_chars/` - 字符搜索（高频）
- `/api/phonology` - 音韵分析（CPU 密集型）
- `/api/get_locs/` - 获取地点列表
- `/api/get_coordinates` - 获取坐标数据
- `/api/get_regions` - 获取区域列表
- `/api/get_custom` - 自定义查询
- `/admin/*` - 管理员端点

## 📈 可以获得的信息

### 1. 性能指标

- **RPS (Requests Per Second)**: 每秒请求数
- **响应时间分布**: P50, P90, P95, P99
- **错误率**: 失败请求的百分比
- **并发能力**: 系统能承载的最大并发用户数

### 2. 资源使用

- **CPU 使用率**: 平均值和峰值
- **内存占用**: 平均值和峰值（MB）
- **线程数**: 应用使用的线程数量
- **连接数**: 活跃的网络连接数

### 3. 瓶颈识别

- **最慢的端点**: 哪个 API 响应最慢
- **CPU vs IO 密集型**: 通过 CPU 使用率判断
- **数据库瓶颈**: 通过连接数和响应时间判断
- **内存泄漏**: 通过内存使用趋势判断

## 🔍 判断 CPU vs IO 密集型

### 方法 1: 观察 CPU 使用率

运行压测时查看 `monitor.py` 的输出：

- **CPU 接近 100%** → CPU 密集型
  - 例如: `/api/phonology` (Pandas 数据处理)
  - 优化方向: 算法优化、使用 Cython、减少计算

- **CPU 低于 50%，但响应慢** → IO 密集型
  - 例如: `/api/search_chars/` (数据库查询)
  - 优化方向: 数据库索引、连接池、缓存

### 方法 2: Worker 数量测试

```bash
# 测试不同 worker 数量的性能
for workers in 2 4 8 16; do
    echo "Testing with $workers workers..."
    # 启动应用并压测
    # 记录 RPS
done
```

- **增加 worker 性能提升明显** → IO 密集型
- **增加 worker 性能不变或下降** → CPU 密集型（GIL 限制）

## 🎯 确定最佳 Worker 数量

### 经验公式

```python
# IO 密集型应用（数据库查询为主）
workers = (2 × CPU核心数) + 1

# CPU 密集型应用（计算为主）
workers = CPU核心数

# 混合型应用（您的情况）
workers = CPU核心数 + 2
```

### 实验方法

创建测试脚本 `test_workers.sh`:

```bash
#!/bin/bash

for workers in 2 4 6 8 12 16; do
    echo "=== Testing with $workers workers ==="

    # 启动应用
    gunicorn -w $workers -k uvicorn.workers.UvicornWorker \
      -b 0.0.0.0:5000 app.main:app &
    PID=$!
    sleep 5

    # 运行压测
    locust -f locustfile.py --host http://localhost:5000 \
      --headless -u 100 -r 10 -t 60s --html report_${workers}w.html

    # 停止应用
    kill $PID
    sleep 2
done
```

查看每个报告的 RPS，选择性能最好的 worker 数量。

## 🔧 函数级性能分析

### 使用 py-spy（推荐）

```bash
# 安装
pip install py-spy

# 实时查看函数调用
py-spy top --pid <进程ID>

# 生成火焰图（运行 60 秒）
py-spy record -o flamegraph.svg --pid <进程ID> --duration 60

# 在浏览器中打开 flamegraph.svg 查看
```

### 使用 cProfile

在 `run.py` 中添加：

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# ... 运行应用 ...

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)  # 显示前 20 个最耗时函数
```

## 💡 测试建议

### 1. 渐进式压测

```bash
# 第一轮: 轻量测试（10 用户）
locust -f locustfile.py --host http://localhost:5000 \
  --headless -u 10 -r 2 -t 2m

# 第二轮: 中等压力（50 用户）
locust -f locustfile.py --host http://localhost:5000 \
  --headless -u 50 -r 5 -t 5m

# 第三轮: 高压力（100 用户）
locust -f locustfile.py --host http://localhost:5000 \
  --headless -u 100 -r 10 -t 10m

# 第四轮: 极限测试（200+ 用户）
locust -f locustfile.py --host http://localhost:5000 \
  --headless -u 200 -r 20 -t 10m
```

### 2. 关注的指标

- **响应时间 P95 < 500ms**: 95% 的请求在 500ms 内完成
- **错误率 < 1%**: 失败请求少于 1%
- **内存稳定**: 不持续增长（排除内存泄漏）
- **CPU 使用合理**: 不超过 80%（留有余地）

### 3. 测试场景

- **正常负载**: 模拟日常使用（50 用户）
- **峰值负载**: 模拟高峰期（100-200 用户）
- **极限负载**: 找到系统崩溃点（持续增加用户）
- **持久测试**: 长时间运行（1-2 小时）检测内存泄漏

## 🐛 常见问题

### Q: 测试时出现大量 401 错误？
A: 检查 `config.py` 中的测试用户是否已创建，密码是否正确。

### Q: 无法连接到服务器？
A: 确认 FastAPI 应用已启动，检查 `config.py` 中的 `BASE_URL` 是否正确。

### Q: monitor.py 找不到进程？
A: 使用 `ps aux | grep uvicorn` 查找进程 ID，然后用 `--pid` 参数指定。

### Q: Windows 上运行 Locust 报错？
A: 确保已安装 Python 3.8+，使用 `pip install --upgrade locust` 更新到最新版本。

## 📝 输出文件

- `performance_metrics_*.json` - 性能监控数据
- `locust_report_*.html` - Locust 测试报告（使用 `--html` 参数）
- `flamegraph.svg` - 火焰图（使用 py-spy 生成）

## ⚠️ 注意事项

1. **不要对生产环境进行高强度压测**，除非您知道自己在做什么
2. **测试前备份数据库**，避免测试数据污染生产数据
3. **监控服务器资源**，避免压测导致服务器崩溃
4. **逐步增加负载**，不要一开始就用最大并发
5. **测试用户权限**，确保测试用户有足够的 API 配额

## 📚 更多资源

- [Locust 官方文档](https://docs.locust.io/)
- [py-spy 文档](https://github.com/benfred/py-spy)
- [FastAPI 性能优化指南](https://fastapi.tiangolo.com/deployment/concepts/)
