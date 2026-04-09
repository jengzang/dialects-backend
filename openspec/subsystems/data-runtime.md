# 数据与运行时规格

> Status: active  
> Scope: `data/*.db`, `app/common`, `app/sql`, 缓存、运行模式、性能约束

## 1. 数据平台定位

本仓库是多数据库 SQLite 架构，不是单库单 schema 架构。

当前主要数据库包括：

- `auth.db`
- `logs.db`
- `characters.db`
- `dialects_admin.db`
- `dialects_user.db`
- `query_admin.db`
- `query_user.db`
- `supplements.db`
- `villages.db`
- `yubao.db`

## 2. 数据库边界规则

### 核心查询数据

- `characters.db`
- `dialects_user.db`
- `query_user.db`

### 认证与后台数据

- `auth.db`
- `logs.db`

### 用户扩展数据

- `supplements.db`

### VillagesML 数据

- `villages.db`

### 规则

1. 新功能先确认应该落在哪一类数据库，而不是直接“找个库先塞进去”。
2. 若一个能力跨多库，必须明确哪一库是权威来源。

## 3. Redis 与缓存规则

当前仓库存在 Redis 与 dummy redis 双态。

### 规则

1. `WEB` 模式可以使用真实 Redis。
2. `MINE/EXE` 必须允许在 dummy redis 下正确运行。
3. 缓存只能优化性能，不应成为功能正确性的唯一来源。

## 4. 性能规则

这是一个明显的数据密集型仓库，性能问题经常来自：

- SQLite 批量查询
- Python 层数据重组
- 两两比较型算法
- 预计算结果读取

### 规则

1. 先区分瓶颈在：
   - SQL
   - Python 数据结构
   - 算法复杂度
2. 新增大规模计算功能时，应尽量提供阶段耗时观测。
3. 不应默认把“索引不足”当成唯一性能原因。

## 5. 运行模式与性能观测

`WEB/MINE/EXE` 下行为不同，因此性能实验必须注明运行模式。

### 规则

1. 任何性能结论都应说明运行模式。
2. 若本地测试使用 `MINE`，不能把 `WEB` 特有的 Redis 延迟误判成算法瓶颈。

## 6. 迁移与索引

索引、表结构和迁移属于长期约束。

### 规则

1. 若新增计算功能依赖某个大表的扫描，应先验证现有索引是否足够。
2. 若结论是“索引不是瓶颈”，应把注意力转向算法和数据组织，而不是继续盲目加索引。
3. 新增索引或迁移应说明受影响数据库与表。

## 7. 变更检查清单

改动本子系统时，至少检查：

- 用的是哪一个 `.db`
- Redis 是优化还是依赖
- `WEB/MINE/EXE` 是否一致
- 是否需要阶段级性能观测
- 是否需要同步更新长期数据边界说明
