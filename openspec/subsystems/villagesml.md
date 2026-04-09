# VillagesML 规格

> Status: active  
> Scope: `app/villagesML`

## 1. 子系统定位

`villagesML` 是本仓库中的独立大子系统，负责自然村地名分析、区域统计、聚类、语义、空间与计算型工作流。

它不是普通 API 的一个小模块，而是：

- 独立路由装配
- 独立数据表体系
- 独立计算与预计算能力

## 2. 路由边界

统一挂载入口：

- `app/villagesML/__init__.py`

统一前缀：

- `/api/villages`

### 规则

1. `villagesML` 新接口应优先在该子系统内扩展，不应散落到 `app/routes/core/`。
2. `villagesML` 内部可以按领域拆成：
   - `character`
   - `village`
   - `metadata`
   - `semantic`
   - `clustering`
   - `spatial`
   - `patterns`
   - `regional`
   - `compute`
   - `admin`
   - `statistics`

## 3. 计算型与查询型边界

`villagesML` 同时包含：

- 直接查询预计算结果的接口
- 触发计算或读取运行结果的接口

### 规则

1. 变更时必须区分这是“查已有结果”还是“做新的计算”。
2. 计算型接口需要更谨慎地评估性能、缓存和结果表结构。

## 4. 数据边界

该子系统主要依赖：

- `villages.db`

并与普通方言查询数据库体系不同。

### 规则

1. 不应把 `villagesML` 的区域级分析逻辑直接混入普通方言点查询逻辑。
2. 若要复用 `villagesML` 的概念到主站其它模块，应先确认对象层级是否一致。

## 5. 变更检查清单

改动本子系统时，至少检查：

- 是否仍保持 `/api/villages/*` 的统一语义
- 是否区分查询型与计算型能力
- 是否影响 `villages.db` 表结构或预计算结果口径
- 是否把区域级分析误投到点级分析场景
