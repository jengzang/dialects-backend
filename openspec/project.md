# 项目总规格

> Status: active  
> Scope: repository-wide  
> Last reviewed: 2026-04-09

## 1. 项目定位

本仓库是“方言比较小站”的 FastAPI 后端，服务于多类能力：

- 核心方言查询
- 地理匹配与分区
- 用户自定义数据
- 认证与管理员后台
- 工具模块平台
- `villagesML` 地名分析系统

项目不是一个单体单域 API，而是一个**多子系统共享同一应用入口**的后端仓库。

## 2. 应用入口与装配

主入口是：

- `app/main.py`

主路由装配入口是：

- `app/routes/__init__.py`

工具模块装配入口是：

- `app/tools/__init__.py`

`villagesML` 装配入口是：

- `app/villagesML/__init__.py`

### 规则

1. 主应用由 `app/main.py -> setup_routes(app)` 统一完成路由装配。
2. `app/routes/__init__.py` 负责常规业务路由、`tools` 平台、`villagesML`、SQL 路由、日志路由的总挂载。
3. `app/tools/__init__.py` 是所有工具模块的唯一统一挂载入口。
4. `app/villagesML/__init__.py` 是 `villagesML` 全部子路由的统一挂载入口。

## 3. 运行模式

当前仓库存在 3 种运行模式：

- `WEB`
- `MINE`
- `EXE`

### 基本语义

- `WEB`
  - 部署模式
  - 默认关闭公开文档页
  - 使用真实 Redis
  - CORS 受限
- `MINE`
  - 本地/局域网开发模式
  - 文档页开启
  - Redis 走 dummy 实现
- `EXE`
  - 打包运行模式
  - 文档页开启
  - Redis 走 dummy 实现
  - 带额外静态目录与控制台保活逻辑

### 规则

1. 新增功能若依赖 Redis、文件路径或后台服务，必须明确区分 `WEB` 与 `MINE/EXE`。
2. 不能假设本地开发一定连接真实 Redis。
3. 不能把仅适用于 `WEB` 的假设写死在工具模块里。

## 4. 主要子系统边界

本仓库按职责可分为以下长期边界：

- 核心 API
  - `app/routes/core`
  - `app/routes/geo`
  - `app/routes/user`
- 认证与管理员
  - `app/routes/auth.py`
  - `app/routes/admin`
  - `app/service/auth`
  - `app/service/admin`
- 工具平台
  - `app/tools`
- `villagesML`
  - `app/villagesML`
- 日志与统计
  - `app/routes/logging`
  - `app/service/logging`
- SQL 与生命周期平台
  - `app/sql`
  - `app/lifecycle`
  - `app/main.py`
- 数据与基础设施
  - `app/common`
  - `app/sql`
  - `data/*.db`

## 5. 文档分层

当前仓库文档分层应保持如下语义：

- `openspec/`
  - 当前有效规格
- `docs/architecture`
  - 分析性架构文档，可辅助理解
- `docs/implementation`
  - 实现说明、联调说明、功能说明
- `docs/archive`
  - 历史材料

### 规则

1. 如果要定义“当前有效规则”，优先更新 `openspec/`。
2. 如果只是记录一次实现过程，不放进 `openspec/`。

## 6. 新功能接入总规则

### 普通 API

- 优先挂在现有业务边界下：
  - `core`
  - `geo`
  - `user`
  - `auth`
  - `admin`

### 工具型 API

- 必须进入 `app/tools/<tool_name>/`
- 必须通过 `app/tools/__init__.py` 统一挂载

### `villagesML` 功能

- 必须挂在 `app/villagesML/` 子系统内
- 必须通过 `app/villagesML/__init__.py` 统一挂载

## 7. 变更时必须回答的问题

任何中大型改动，至少应回答以下问题：

1. 它属于哪个子系统？
2. 它改变了哪个公开 API 或内部契约？
3. 它依赖哪个数据库或缓存？
4. 它在 `WEB/MINE/EXE` 下是否一致？
5. 它是否需要同步更新 `openspec/`？
