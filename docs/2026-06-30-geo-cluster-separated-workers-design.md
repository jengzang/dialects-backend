# 2026-06-30 geo-cluster-separated-workers design

## 1. 背景与目标

当前后端主应用通过 `app/main.py -> create_app() -> setup_routes()/setup_tools_routes()/setup_villages_routes()` 一次性注册全部路由，并在 `lifespan` 中执行统一的 `run_process_startup()`。

现状里有两类明显不适合继续与主查询 API 共享 worker 的能力：

1. GIS 新路由（AreaCity Python query pipeline）
   - 新增入口为 `app/routes/geo/areacity_query.py`
   - 它依赖 `app/geo_query/*` 的低内存索引/几何引擎
   - 目前在 `app/lifecycle/startup.py` 的 `initialize_geo_query_engine()` 中被所有应用 worker 启动时初始化
2. cluster 路由
   - 主入口为 `app/tools/cluster/routes.py`
   - 其执行链路依赖 `numpy` / `sklearn` / `numba`，并在请求命中后进入较重的计算与缓存路径

用户目标：
- geo 和 cluster 分成两个独立 worker
- 不让主应用现有 3 个 worker 背负这两类能力的常驻或峰值内存
- 暂不直接改运行代码，先形成 repo-grounded 设计方案

本设计只覆盖：
- 新 GIS 路由拆分
- cluster 路由拆分
- 主应用与两个独立 worker 的边界、启动、部署与回退策略

本设计明确不覆盖：
- 老 geo 路由（`get_partitions` / `locations` / `get_regions` / `batch_match` / `get_coordinates` / `get_locs`）的迁移
- villagesML 里其他重模块的进一步拆分
- 网关、前端、鉴权产品语义的大改

## 2. 已确认的当前代码事实

### 2.1 主应用启动与资源初始化

主入口：`app/main.py`

- `app = create_app()` 创建唯一大应用
- `lifespan()` 中无条件执行 `run_process_startup()`
- `run_process_startup()` 当前包含：
  - 初始化 DB pools
  - 用户/日志数据库迁移
  - 临时文件清理
  - dialect cache 预热
  - `initialize_geo_query_engine()`

这意味着：
- 只要当前应用 worker 启动，就会执行 geo 引擎初始化
- GIS 新路由虽然只有一部分接口会使用，但内存负担已经在进程启动期进入了所有 worker 的生命周期

### 2.2 新 GIS 路由的实际范围

新 GIS 路由入口：`app/routes/geo/areacity_query.py`

当前注册位置：`app/routes/__init__.py`
- `app.include_router(areacity_query_router, prefix="/api", tags=["geo"], ...)`

当前接口范围：
- `GET /api/gis/status`
- `GET /api/gis/query/point`
- `GET /api/gis/query/point-with-tolerance`
- `POST /api/gis/query/geometry`
- `GET /api/gis/boundary/by-id`
- `GET /api/gis/search`
- `GET /api/gis/children`

依赖链路：
- `app/routes/geo/areacity_query.py`
- `app/geo_query/loader.py`
- `app/geo_query/engine.py`
- `app/geo_query/config.py`
- `app/geo_query/index_store.py`
- `app/geo_query/query_ops.py`
- `app/geo_query/geometry_store.py`
- `app/geo_query/geometry_utils.py`

### 2.3 老 geo 路由仍在主应用中

当前仍由 `app/routes/__init__.py` 注册：
- `app/routes/geo/get_partitions.py`
- `app/routes/geo/locations.py`
- `app/routes/geo/get_regions.py`
- `app/routes/geo/batch_match.py`
- `app/routes/geo/get_coordinates.py`
- `app/routes/geo/get_locs.py`

这些接口大量依赖：
- query DB
- user/custom DB
- dialect cache
- `app.service.geo.*`

本次设计不迁移它们，避免把“新 GIS 引擎拆分”扩成“整个 geo 域重构”。

### 2.4 cluster 路由的实际范围

主入口：`app/tools/cluster/routes.py`

当前注册位置：`app/tools/__init__.py`
- `app.include_router(cluster_router, prefix="/api/tools/cluster", tags=["工具-Cluster"], ...)`

该入口已经做过一层延迟导入，`routes.py` 内通过 `_cluster_service()` / `_cluster_cache_service()` 等函数在请求期拉起核心模块。

核心依赖与风险模块：
- `app/tools/cluster/service/cluster_service.py`
  - `import numpy as np`
- `app/tools/cluster/service/distance_service.py`
  - `import numpy as np`
  - `from numba import njit, prange, threading_layer`
- `app/tools/cluster/service/pipeline_service.py`
  - `sklearn.cluster`
  - `sklearn.mixture`
  - `sklearn.preprocessing`
  - `sklearn.decomposition`
  - `sklearn.metrics`

辅助依赖：
- Redis：`app/tools/cluster/service/cache_service.py`
- 任务状态/结果文件：`app/tools/cluster/service/task_service.py`
- 本地任务状态文件：`app/tools/task_manager.py`
- dialect/query DB：通过依赖注入进入

### 2.5 运行模式与 Redis 约束

`app/redis_client.py` 显示：
- `_RUN_TYPE == 'WEB'` 才启用真实 Redis
- 其他模式使用 DummyRedis

这意味着：
- cluster 独立 worker 若需要保留当前缓存/inflight 去重语义，必须继续运行在 `WEB` 模式或等价 Redis 可用模式
- gis worker 是否强依赖 Redis：不强依赖；其核心是 `app/geo_query/engine.py` 的内存索引 + 几何缓存

### 2.6 Gunicorn 当前形态

`gunicorn_config.py`：
- 当前只有一套 app 的 gunicorn 配置
- 绑定 `0.0.0.0:5000`
- `workers = 3`
- master 进程启动 background services
- worker 退出时清理 DB pools

这说明当前部署模型是：
- 一个大 app
- 3 个同构 worker
- 所有 worker 共同承接主查询、老 geo、新 GIS、cluster、villagesML、工具路由等

## 3. 设计目标

### 3.1 主要目标

1. 主应用 worker 不再初始化 geo query engine
2. 主应用 worker 不再承接 `/api/tools/cluster/**`
3. gis 与 cluster 各自有独立 worker 进程池，可单独调 worker 数
4. 尽量复用现有业务模块，不重写 geo/cluster 核心实现
5. 对前端/调用方尽可能保持路径不变，通过反向代理/网关按 path 分流

### 3.2 非目标

1. 不追求一次性把所有重模块拆成微服务
2. 不把老 geo 路由一起迁走
3. 不修改 cluster 的业务协议、任务协议和结果结构
4. 不修改新 GIS 接口的 URL 结构

## 4. 方案候选

### 方案 A：一个 heavy app，内含 gis + cluster

做法：
- 新建一个 `heavy app`
- 主 app 去掉新 GIS 路由与 cluster 路由
- heavy app 同时注册 `areacity_query_router` 与 `cluster_router`

优点：
- 改动较小
- 只多一套部署

缺点：
- gis 常驻索引与 cluster 峰值计算共处一池
- cluster 的慢任务/高 CPU 峰值可能影响 gis 查询响应
- 后续若要继续细分，还要再拆第二次

结论：不推荐作为目标态，只适合极短期过渡。

### 方案 B：gis worker 与 cluster worker 完全独立

做法：
- 主 app：只保留原主业务、老 geo、普通 query、普通 tools/villages 路由
- gis app：只注册新 GIS 路由，并只做 geo 引擎初始化
- cluster app：只注册 cluster 路由，并保留 cluster 现有 Redis/任务/结果文件机制
- 外层代理按 path 转发：
  - `/api/gis/**` -> gis app
  - `/api/tools/cluster/*` -> cluster app
  - 其他 -> main app

优点：
- 目标清晰，真正把两类内存风险从主 worker 剥离
- gis 与 cluster 资源画像不同，可以独立调优
- 后续扩展最自然

缺点：
- 需要 3 套 app 入口/3 套 gunicorn 配置/代理分流
- 需要仔细处理 shared startup、logging、中间件与静态资源边界

结论：推荐方案。

### 方案 C：单代码库，多 app factory + 公共装配层

做法：
- 在方案 B 基础上，把 app 装配进一步抽象成公共工厂：
  - `create_main_app()`
  - `create_gis_app()`
  - `create_cluster_app()`
- 公共中间件、公共 lifespan 片段、公共 limiter/logging 装配通过参数化函数复用

优点：
- 长期最整洁
- 避免 3 份 app 入口复制粘贴

缺点：
- 设计期复杂度更高
- 若一次性抽象过度，容易引入额外风险

结论：推荐作为实现方式，但按“先可运行，再抽象”的节奏落地。也就是说，目标架构采用 B，代码组织方式采用 C。

## 5. 推荐目标架构

采用：方案 B + 方案 C 的组合。

即：
- 部署拓扑上，使用 3 个独立 app/worker 池
- 代码组织上，使用共享 app factory / route assembly / startup profile

### 5.1 三个应用的职责边界

#### main app
职责：
- 承接主业务与现有大部分 API
- 保留老 geo 路由
- 保留普通 query / auth / user / admin / villagesML / 其他 tools
- 不注册新 GIS 路由
- 不注册 cluster 路由
- 不初始化 geo query engine

必须排除：
- `app.routes.geo.areacity_query`
- `app.tools.cluster.routes`
- geo engine startup profile

#### gis app
职责：
- 只承接新 GIS 路由
- 负责 AreaCity 引擎初始化
- 可以共享 DB pool / 基础日志 / limiter / gzip / cors 中间件
- 不注册老 geo 路由
- 不注册 cluster 路由
- 不启动 villages/tools 全量装配

必须包含：
- `app/routes/geo/areacity_query.py`
- `initialize_geo_query_engine()`

应排除：
- cluster 路由
- villagesML
- tools 全量注册
- 老 geo 路由

#### cluster app
职责：
- 只承接 `/api/tools/cluster/**`
- 继续使用当前 cluster Redis、task_manager、结果文件落盘与 staged/inflight 机制
- 不初始化 geo query engine
- 不注册其他 tools

必须包含：
- `app/tools/cluster/routes.py`
- Redis 可用运行模式
- cluster 所需 DB selector / task manager / file manager / logging middleware / limiter

应排除：
- 新 GIS
- 老 geo
- 其他 tools
- villagesML（除非未来另行拆分）

## 6. 代码组织设计

### 6.1 建议新增的 app factory 结构

建议新增一个装配层，而不是继续只靠一个 `app/main.py`。

建议结构：
- `app/app_factory.py`
  - `create_base_app(profile: str)`
  - `configure_common_middleware(app, profile)`
  - `configure_static_mounts(app, profile)`
  - `configure_lifespan(profile)`
- `app/app_profiles.py`
  - 定义 `main` / `gis` / `cluster` 的 profile 行为
- `app/entrypoints/main_app.py`
  - `app = create_main_app()`
- `app/entrypoints/gis_app.py`
  - `app = create_gis_app()`
- `app/entrypoints/cluster_app.py`
  - `app = create_cluster_app()`

保留：
- `app/main.py`
  - 第一阶段可保持兼容
  - 第二阶段可逐步变成 `main_app.py` 的简单转发或废弃

### 6.2 路由装配拆分

当前：
- `app/routes/__init__.py -> setup_routes(app)`
- `app/tools/__init__.py -> setup_tools_routes(app)`
- `app/villagesML/__init__.py -> setup_villages_routes(app)`

建议拆成：

1. 主路由装配
- `setup_main_routes(app)`
- 在现有 `setup_routes(app)` 基础上去掉 `areacity_query_router`

2. 新 GIS 装配
- `setup_gis_query_routes(app)`
- 只注册 `areacity_query_router`

3. tools 装配分裂
- `setup_tools_routes(app)` 保留现状但拆为更细粒度函数
- 新增：
  - `setup_cluster_tool_routes(app)`
  - `setup_non_cluster_tool_routes(app)`

cluster app 只调 `setup_cluster_tool_routes(app)`。
main app 调 `setup_non_cluster_tool_routes(app)`。

### 6.3 startup profile 拆分

当前 `run_process_startup()` 把所有启动动作绑在一起，导致 gis app 与主 app 无法分离。

建议把 startup 拆成独立片段：
- `initialize_db_pools()`
- `migrate_user_region_tables()`
- `migrate_logs_database()`
- `cleanup_old_temp_files()`
- `warm_dialect_cache()`
- `initialize_geo_query_engine()`

在此基础上增加 profile 化编排：

- `run_main_startup()`
  - DB pools
  - user/logs migration
  - cleanup
  - dialect cache warmup
  - 不做 geo engine init

- `run_gis_startup()`
  - DB pools（可选，若未来 GIS 只用静态索引可进一步收缩）
  - cleanup（可选）
  - geo engine init
  - 不做 dialect cache warmup

- `run_cluster_startup()`
  - DB pools
  - cleanup
  - 可选 dialect cache warmup（如果 cluster 首次请求严重依赖该缓存，建议保留）
  - 不做 geo engine init

## 7. 部署与路由分流设计

### 7.1 外层访问路径保持不变

推荐不修改前端/调用方路径，而由反向代理按 path 分流。

分流规则：

- main upstream
  - 除以下特殊路径外的全部请求

- gis upstream
  - `/api/gis/**`

- cluster upstream
  - `/api/tools/cluster/`
  - 以及其全部子路径

注意：
- 不再需要维护“新 geo 白名单路径”
- 老 geo 路由继续保留在 main app 的 `/api/geo/**` 命名空间下
- 新 GIS 路由完全使用 `/api/gis/**`，与老 geo 前缀分离

### 7.2 gunicorn 建议

建议最终存在 3 套配置：
- `gunicorn_main.py`
- `gunicorn_gis.py`
- `gunicorn_cluster.py`

建议初始 worker 数：
- main: 3
- gis: 1
- cluster: 1

后续按压测再调。

建议端口示例：
- main: 5000
- gis: 5001
- cluster: 5002

### 7.3 各 worker 的并发建议

#### gis worker
- 初始 1 worker
- 原因：GIS engine 会持有索引/元数据/几何缓存；worker 增加意味着内存线性复制
- 若查询流量大，优先先观察单 worker 响应，再评估是否通过增加 worker 还是上更强实例

#### cluster worker
- 初始 1 worker
- 原因：cluster 计算本身就重，`numpy/sklearn/numba` + 距离矩阵/聚类中间结果都可能吃内存
- 若需要并发，优先评估：
  - 单 worker + 任务排队是否可接受
  - 若不可接受，再升到 2，但要先验证内存上限

## 8. 边界条件与风险点

### 8.1 不再把新 old/new geo 混前缀

本次改为硬切换：
- 新 AreaCity 路由统一进入 `/api/gis/**`
- 老 geo 路由继续保留在 `/api/geo/**`

结论：
- 代理层可以直接把整个 `/api/gis/**` 切到 gis worker
- 不再需要针对新 geo 做精确白名单分流

### 8.2 主 app 必须停止 geo engine startup

这是本次内存优化能否真正生效的核心点。

如果只把新 GIS 路由分流出去，但 main app 仍执行：
- `run_process_startup() -> initialize_geo_query_engine()`

那么主 app 仍然会背 geo 引擎内存，拆分就失去主要意义。

### 8.3 cluster 依赖 Redis，不能错误降级到 DummyRedis

因为：
- `app/tools/cluster/service/cache_service.py` 用同步 Redis 做结果缓存、inflight 去重
- `_RUN_TYPE != WEB` 时会变成 DummyRedis

若 cluster 独立 worker 未运行在 Redis 可用模式：
- 结果缓存失效
- inflight 去重失效
- staged prepare/distance 缓存失效
- 可能导致重复计算和更高 CPU/内存峰值

### 8.4 cluster task_manager 是本地文件状态，不适合多实例共享同一路径但无协调

`app/tools/task_manager.py` 当前是文件型任务状态管理器：
- task 状态写 JSON
- 结果写文件
- 依赖本地文件系统

这意味着：
- 单个 cluster app + 单机 worker 池问题不大
- 若未来扩成多台 cluster 机器，任务状态与结果文件要么共享存储，要么改造为集中式元数据存储

本次设计先假设：
- 仍是单机内多进程部署
- cluster app 的本地 task 目录对该 app 的 worker 共享可见

### 8.5 geo engine 的“低内存”不等于“零内存”

`app/geo_query/engine.py` 虽然是 lowmem 设计：
- 几何数据在文件里
- 部分按需读取

但仍会常驻：
- features
- index_records
- grid_index / subgrid_index
- geometry LRU cache

因此：
- gis app worker 数仍要谨慎
- 不应像普通轻路由一样开多 worker

### 8.6 background services 不能在三套 app 上重复乱启

当前 `gunicorn_config.py` 的 master 会启：
- logging workers
- scheduler
- periodic cleanup

如果三套 gunicorn 都复用同样的 master hooks 且不加区分：
- scheduler 可能重复启动 3 份
- cleanup 线程可能重复做同类工作
- logging worker 可能重复占资源

因此必须设计“哪些 app 允许启动 background master services”。

推荐：
- 只有 main app 启动全量 background services
- gis app、cluster app 默认不开 scheduler / logging worker master sidecar
- gis/cluster app 只保留自身 request 处理所需的最小 shutdown cleanup

这是一个关键边界条件。

## 9. 推荐的启动/后台服务策略

### 9.1 main app
- 保留当前 background services 启动资格
- 作为系统主实例，负责 scheduler / logging worker / periodic cleanup

### 9.2 gis app
- 不启动 scheduler
- 不启动 logging worker sidecar master
- 不启动 periodic cleanup thread（除非以后确认它负责 GIS 专属产物清理）
- 只保留 request middleware + lifespan 中最小资源初始化/释放

### 9.3 cluster app
- 默认也不启动 scheduler
- 默认不启动 logging worker sidecar master
- cleanup 可以两种策略二选一：
  1. 只由 main app 的 cleanup 统一清理 cluster 产物
  2. cluster app 只清理 cluster task 目录

推荐先用策略 1，避免多实例重复清理。

## 10. 推荐实施顺序

### 第 1 阶段：代码结构可支持三 app，但不切流量

目标：
- 提取 app factory
- 拆 route assembly
- 拆 startup profile
- 新建三套 entrypoint
- 保持现有 main app 行为先不变或兼容可回退

验收：
- main/geo/cluster 三个 app 都能单独启动
- gis app 只暴露新 GIS 路由
- cluster app 只暴露 cluster 路由

### 第 2 阶段：停掉主 app 的 geo/cluster 装配

目标：
- main app 不再注册新 GIS 路由
- main app 不再注册 cluster 路由
- main app startup 不再初始化 geo engine

验收：
- 主 app 内存明显下降
- 主 app 访问新 GIS / cluster 路径时应由外层代理转发，不再本地命中

### 第 3 阶段：反向代理切流

目标：
- `/api/gis/**` -> gis upstream
- `/api/tools/cluster/**` -> cluster upstream
- 其他 -> main upstream

验收：
- 前端与调用方 URL 不变
- 新 GIS 与 cluster 请求命中对应 worker
- 老 geo 仍命中 main app

### 第 4 阶段：压测与参数调优

重点观察：
- main app RSS/峰值是否下降
- gis app 常驻内存
- cluster app 峰值内存、任务排队时间、失败率
- Redis 命中与 inflight 去重是否正常

## 11. 回退方案

设计上必须允许快速回退。

推荐回退路径：
- 保留 main app 旧入口一段时间
- 反向代理只需改回全部指向 main upstream
- 代码层通过 feature flag 或 profile 控制：
  - main app 是否注册 `areacity_query_router`
  - main app 是否注册 `cluster_router`
  - main app 是否执行 `initialize_geo_query_engine()`

这样即使 gis/cluster 独立 worker 出问题，也能快速回切。

## 12. 最终推荐结论

推荐采用“三 app、双专用 worker 池”的拆分方案：

1. main app
- 保留主业务与老 geo
- 不注册新 GIS
- 不注册 cluster
- 不初始化 geo engine

2. gis app
- 只承接新 GIS 路由
- 只初始化 geo engine
- 初始 1 worker

3. cluster app
- 只承接 `/api/tools/cluster/**`
- 保留 Redis 缓存、task_manager、结果落盘机制
- 初始 1 worker

这是当前项目里最符合目标且边界清晰的方案，因为它：
- 直接命中主 worker 内存痛点
- 不需要重写 geo/cluster 核心业务
- 不会把老 geo 路由一起卷进本次改造
- 能为后续 villagesML / praat / check 等重模块继续拆分留下清晰模板

## 13. 实施前需要额外确认的少量决策

### 决策 1：是否接受将新 AreaCity 路由硬切换到 `/api/gis/**`
推荐：接受。
原因：这样可以彻底避免新老 geo 共用前缀，代理层无需维护新 GIS 白名单。

### 决策 2：cluster app 是否接受“单 worker 排队优先”
推荐：接受。
原因：先优先保证主 app 内存隔离，再根据压力决定是否加到 2 worker。

### 决策 3：background services 是否只保留在 main app
推荐：是。
原因：避免三套 gunicorn 重复启动 scheduler / cleanup / logging sidecar。
