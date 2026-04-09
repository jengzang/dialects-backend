# OpenSpec

> Status: active  
> Last reviewed: 2026-04-09

`openspec/` 是当前仓库的长期规格目录，用来描述**当前仍然有效**、并且应当被后续协作者持续遵守的系统边界、模块职责和扩展规则。

它和 `docs/` 的分工是：

- `openspec/`
  - 放当前有效的系统规格
  - 强调边界、契约、职责、约束
  - 面向未来维护者
- `docs/`
  - 放教程、说明、实现记录、历史方案、前后端联调文档
  - 可以包含阶段性内容
- `docs/archive/`
  - 放历史实现记录、旧方案、已失效决策

## 目录说明

- [`project.md`](./project.md)
  - 项目总览、运行模式、应用入口、主路由装配
- [`subsystems/core-api.md`](./subsystems/core-api.md)
  - 核心查询、地理、用户自定义数据相关 API 规格
- [`subsystems/auth-admin.md`](./subsystems/auth-admin.md)
  - 认证、会话、管理员相关规格
- [`subsystems/tools-platform.md`](./subsystems/tools-platform.md)
  - `app/tools/` 平台与工具模块规格
- [`subsystems/villagesml.md`](./subsystems/villagesml.md)
  - `villagesML` 子系统规格
- [`subsystems/data-runtime.md`](./subsystems/data-runtime.md)
  - 数据库、缓存、运行模式、性能约束规格
- [`subsystems/platform-observability.md`](./subsystems/platform-observability.md)
  - SQL 路由、日志统计、限流与应用生命周期规格

## 使用规则

1. 如果一个改动改变了**长期有效的边界或契约**，应同步更新对应 OpenSpec。
2. 如果一个改动只是一次性实现过程、实验记录或阶段性方案，不应写进 `openspec/`。
3. OpenSpec 优先描述：
   - 代码边界
   - 路由边界
   - 数据存储边界
   - 运行模式差异
   - 扩展规则
4. OpenSpec 不替代源码。它回答的是：
   - 这个子系统负责什么
   - 不负责什么
   - 改动时必须遵守哪些规则
   - 新功能应挂到哪里

## 维护约定

- 新增复杂子系统时，优先新增一份子系统规格，而不是把规则散落在多个 `docs/*.md`。
- 若某份 OpenSpec 已失效，应在同一 PR 中更新或删除，不保留“明知过时”的规格。
- 过程性设计稿不放这里。
