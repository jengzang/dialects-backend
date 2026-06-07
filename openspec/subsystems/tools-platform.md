# Tools 平台规格

> Status: active  
> Scope: `app/tools`, `app/tools/__init__.py`, `app/tools/file_manager.py`, `app/tools/task_manager.py`

## 1. 平台定位

`app/tools/` 是工具类 API 模块的统一平台，不是普通业务路由的杂项目录。

它承担两类职责：

- 工具模块目录
  - 例如 `check`、`jyut2ipa`、`merge`、`praat`、`cluster`
- 工具模块共用基础设施
  - `app/tools/file_manager.py`
  - `app/tools/task_manager.py`

## 2. 唯一挂载方式

所有工具模块都必须通过：

- `app/tools/__init__.py`

统一挂载到主应用。

### 规则

1. 工具模块内部只暴露 `router = APIRouter()`。
2. 工具模块内部不应自带全局 prefix。
3. 工具模块内部不应各自实现第二套全局挂载规则。

## 3. 适合进入 Tools 的功能

以下情况优先考虑进入 `app/tools/`：

- 有明确任务生命周期
- 有结果落盘或文件管理需求
- 有后台执行和状态轮询需求
- 语义上更像“工具”而不是常规业务查询

### 反例

以下情况通常不应进入 `app/tools/`：

- 普通同步查询接口
- 单纯的 CRUD 接口
- 仅管理员可见的后台管理能力

## 4. 工具模块结构规则

简单工具可小而平；复杂工具可分层。

当前仓库中：

- `cluster`
  - 已采用 `config + schemas + service + utils + routes`
- `praat`
  - 采用较复杂的 `core + schemas + utils + routes`

### 规则

1. 复杂工具可以比普通工具目录更复杂。
2. 但无论内部结构如何，都必须服从统一挂载方式。
3. 新工具若复用 `task_manager/file_manager`，就应被视为平台内正式工具模块。

## 5. `task_manager` 与 `file_manager`

这两个模块是平台级共享基础设施。

### 规则

1. 工具模块应适配它们，而不是各自改写平台规则。
2. 若某工具模块需要特殊状态表达或结果布局，应在工具模块自身做适配层。
3. 不应为单个工具模块修改成熟平台逻辑，除非是平台级通用改进。

## 6. `cluster` 与 `praat` 的示范意义

- `cluster`
  - 说明“复杂算法 + 任务型接口”应进入 `tools`
- `praat`
  - 说明“复杂工具可以拥有更明显的内部子系统结构”

这两个模块应被视为今后复杂工具接入时的优先参考对象。

## 7. 变更检查清单

改动本子系统时，至少检查：

- 新模块是否通过 `app/tools/__init__.py` 挂载
- 是否误改了 `task_manager/file_manager` 的平台语义
- 工具职责是否与普通业务 API 混淆
- 复杂工具是否仍维持清晰的内部分层
