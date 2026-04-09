# Core API 规格

> Status: active  
> Scope: `app/routes/core`, `app/routes/geo`, `app/routes/user`

## 1. 负责范围

本子系统负责非管理员、非工具、非 `villagesML` 的常规业务接口，包括：

- 核心方言查询
- 比较与检索
- 地理匹配、地点与分区查询
- 用户自定义查询与自定义分区数据

主要代码边界：

- `app/routes/core/`
- `app/routes/geo/`
- `app/routes/user/`
- 对应的 `app/service/geo/`

## 2. 路由装配规则

这些路由统一由：

- `app/routes/__init__.py`

直接挂到主应用。

### 规则

1. 普通业务 API 不应绕过 `app/routes/__init__.py` 自行挂载。
2. 新增核心查询接口，优先复用 `app/routes/core` 现有边界。
3. 新增地理匹配/分区接口，优先复用 `app/routes/geo`。

## 3. 查询口径

该子系统以“查询、比较、获取结构化数据”为主，不负责：

- 长任务型工具执行
- 文件管理型任务
- `villagesML` 的区域计算工作流

### 规则

1. 如果功能天然需要任务状态、文件落盘、结果回读，应优先评估是否属于 `app/tools/`。
2. 如果功能是普通同步查询，不应为了形式统一而强行做成工具模块。

## 4. 地理输入规则

当前仓库的地点与分区输入存在统一惯例：

- `locations`
- `regions`
- `region_mode` / `regiontype`

相关能力主要由：

- `app/service/geo/getloc_by_name_region.py`
- `app/service/geo/match_input_tip.py`

提供。

### 规则

1. 新接口若需要地点/分区输入，应优先复用现有解析逻辑。
2. 不应在不同模块中反复发明不同的地点字段命名。

## 5. 用户数据边界

`app/routes/user/` 负责用户可维护的自定义数据入口，但不负责认证主流程。

### 规则

1. 用户态自定义数据接口不应直接扩散到 `app/routes/core/`。
2. 认证、权限和管理员逻辑必须仍回到对应子系统。

## 6. 变更检查清单

改动本子系统时，至少检查：

- 是否破坏现有地点输入口径
- 是否误把长任务功能塞进普通同步路由
- 是否新增了与 `tools` 或 `villagesML` 重叠的能力
- 是否需要补充前端可消费的字段说明
