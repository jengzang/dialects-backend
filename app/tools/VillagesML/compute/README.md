# Compute Module

在线计算模块 - 提供参数化的实时分析接口

## 模块结构

```
api/compute/
├── __init__.py          # 模块初始化
├── cache.py             # 缓存管理（LRU + TTL）
├── validators.py        # 参数验证（Pydantic）
├── timeout.py           # 超时控制
├── engine.py            # 计算引擎（聚类、语义、特征）
├── clustering.py        # 聚类API端点
├── semantic.py          # 语义分析API端点
├── features.py          # 特征提取API端点
├── subset.py            # 子集分析API端点
└── models.py            # 响应模型
```

## 核心组件

### 1. 缓存层 (cache.py)

```python
from api.compute.cache import compute_cache

# 获取缓存
result = compute_cache.get("endpoint_name", params)

# 设置缓存
compute_cache.set("endpoint_name", params, result)

# 获取统计
stats = compute_cache.get_stats()
```

### 2. 计算引擎 (engine.py)

```python
from api.compute.engine import ClusteringEngine

engine = ClusteringEngine(db_path)
result = engine.run_clustering(params)
```

### 3. 超时控制 (timeout.py)

```python
from api.compute.timeout import timeout

with timeout(5):  # 5秒超时
    result = expensive_computation()
```

## API端点

### 聚类分析

- `POST /api/compute/clustering/run` - 执行聚类
- `POST /api/compute/clustering/scan` - 参数扫描
- `GET /api/compute/clustering/cache-stats` - 缓存统计
- `DELETE /api/compute/clustering/cache` - 清除缓存

### 语义分析

- `POST /api/compute/semantic/cooccurrence` - 共现分析
- `POST /api/compute/semantic/network` - 语义网络

### 特征提取

- `POST /api/compute/features/extract` - 批量提取
- `POST /api/compute/features/aggregate` - 区域聚合

### 子集分析

- `POST /api/compute/subset/cluster` - 子集聚类
- `POST /api/compute/subset/compare` - 子集对比

## 使用示例

### Python客户端

```python
import requests

# 聚类分析
response = requests.post(
    "http://localhost:8000/api/compute/clustering/run",
    json={
        "algorithm": "kmeans",
        "k": 4,
        "region_level": "county",
        "features": {
            "use_semantic": True,
            "use_morphology": True
        }
    }
)

result = response.json()
print(f"Silhouette: {result['metrics']['silhouette_score']:.3f}")
print(f"From cache: {result['from_cache']}")
```

## 配置

在 `api/config.py` 中配置：

```python
# 计算超时
COMPUTE_TIMEOUT = 5  # 秒

# 缓存配置
COMPUTE_CACHE_SIZE = 100  # 条目数
COMPUTE_CACHE_TTL = 3600  # 秒
```

## 性能特性

- **缓存**: LRU + TTL策略，自动缓存相同参数的结果
- **超时**: 防止长时间运行阻塞服务器
- **验证**: Pydantic严格参数验证
- **限制**: 数据规模和参数范围限制

## 开发指南

### 添加新端点

1. 在 `validators.py` 添加参数模型
2. 在 `engine.py` 添加计算逻辑
3. 在对应的API文件添加端点
4. 在 `main.py` 注册路由

### 测试

```bash
# 运行测试
python tests/test_compute_api.py

# 单元测试
pytest tests/test_compute_*.py
```

## 文档

- 完整文档: `docs/ONLINE_COMPUTE_API_IMPLEMENTATION.md`
- 快速开始: `docs/ONLINE_COMPUTE_API_QUICKSTART.md`
- 实现总结: `docs/ONLINE_COMPUTE_API_SUMMARY.md`

## 依赖

- FastAPI >= 0.104.0
- Pydantic >= 2.0.0
- scikit-learn >= 1.3.0
- NumPy >= 1.24.0
- Pandas >= 2.0.0

## 许可

与主项目相同
