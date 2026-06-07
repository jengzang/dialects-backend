# 平台与可观测性规格

> Status: active  
> Scope: `app/sql`, `app/routes/logging`, `app/service/logging`, `app/lifecycle`, `app/main.py`

## 1. 子系统定位

这一层不是单一业务域，而是主应用运行所依赖的平台能力集合，包括：

- SQL 浏览与管理路由
- 请求日志、访问统计、限流与诊断
- 进程启动/关闭生命周期
- 后台服务启动与清理

它们共同决定“应用如何运行”和“应用如何被观测”，不应被当成普通业务模块处理。

## 2. SQL 路由边界

统一挂载入口：

- `app/sql/__init__.py`

主要实现边界：

- `app/sql/sql_routes.py`
- `app/sql/sql_tree_routes.py`
- `app/sql/sql_admin_routes.py`
- `app/sql/db_pool.py`
- `app/sql/db_selector.py`

### 规则

1. SQL 相关接口统一通过 `setup_sql_routes(app)` 挂载。
2. SQL 路由属于平台能力，不应和普通业务查询路由混在同一个目录下扩展。
3. 若新增数据库浏览、选择或管理能力，应优先复用 `app/sql/` 现有边界，而不是在业务路由里另做一套。

## 3. 日志与统计边界

统一挂载入口：

- `app/service/logging/__init__.py`

主要实现边界：

- `app/routes/logging/`
- `app/service/logging/core/`
- `app/service/logging/stats/`
- `app/service/logging/middleware/`
- `app/service/logging/dependencies/`

### 规则

1. 请求日志、中间件、统计聚合、限流属于平台层，不属于某个单一业务模块。
2. 若新增访问统计、usage 统计、诊断流水线，应优先进入 `app/service/logging/`。
3. 业务模块可以复用日志与限流能力，但不应各自复制一套请求记录与统计机制。

## 4. 限流与中间件

当前全局限流与请求日志主要由：

- `app.service.logging.dependencies.ApiLimiter`
- `app.service.logging.middleware.traffic_logging.RequestLogMiddleware`

接入。

### 规则

1. 路由层的限流依赖应继续复用统一 `ApiLimiter`。
2. 不应在单个子系统里静默引入第二套全局限流策略。
3. 请求日志中间件属于应用级能力，变更时必须评估对所有路由的影响。

## 5. 生命周期边界

统一生命周期入口：

- `app/main.py`
- `app/lifecycle/__init__.py`

主要实现边界：

- `app/lifecycle/startup.py`
- `app/lifecycle/background.py`
- `app/lifecycle/runtime.py`

### 规则

1. 应用启动、后台服务启动、进程资源释放必须通过 `app/lifecycle/` 统一编排。
2. 新增后台服务时，应接入生命周期层，而不是在任意模块 import 时偷偷启动线程或任务。
3. `WEB` 与 `MINE/EXE` 的进程行为差异，应首先在生命周期层处理。

## 6. 与其它子系统的关系

- 普通业务路由依赖平台层提供限流、日志与生命周期能力。
- `tools` 和 `villagesML` 也复用同一套限流与应用生命周期。
- 平台层不负责定义业务含义，但负责保证业务在统一运行环境中被调度、记录与保护。

## 7. 变更检查清单

改动本子系统时，至少检查：

- 是否影响全局路由挂载与限流依赖
- 是否影响请求日志、usage 或诊断流水线
- 是否改动了 SQL 路由的可访问边界
- 是否改变 `WEB/MINE/EXE` 下的启动与关闭行为
- 是否需要同步更新运行时或可观测性长期规则
