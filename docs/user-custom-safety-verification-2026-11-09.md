# 用户自定义数据安全保存：实现与验证记录

日期：2026-11-09。前后端均直接修改各自现有 `dev`，未提交、未推送、未部署。

## 已实现

- 用户数据读取返回 `id`、`version`、明确带 Z 且保留微秒的 `created_at_utc`，原 created_at 保留兼容。
- 新增 PUT `/user/custom/batch-update`、DELETE `/user/custom/batch-delete-by-id`、POST `/user/custom/save`。
- 整批归属、字段、数量、版本检查；任意无效或数据库中途失败整批回滚。更新保留原 ID、创建时间、存储标记，值变化时重算 maxValue。
- 保存将新增、修改、删除放在同一 BEGIN IMMEDIATE 事务。业务写入与幂等回执一起提交，相同请求键与内容重放返回原回执。
- ORM 版本控制覆盖用户旧编辑、管理员普通 ORM 编辑；旧时间戳写入口遇到多条匹配拒绝执行。管理员遗留时间戳删除也加入唯一性校验，防止新保存批次具有相同时间时误删整个批次。
- 普通用户新旧创建入口统一检查每小时 500、总量 5,000 的配额；检查和写入在同一写事务。管理员豁免明确比较 role。
- 新写请求最多 50 个变更、2 MiB 流式请求体，并限制字段长度。每 worker 最多 1 个本功能用户写事务，竞争时立即 429，不新增 worker 或常驻服务。
- 前端用户页、地点编辑、特征弹窗/表格、地图侧栏全部迁移新写接口。地图弹出点从查询结果到地图分组保留每条记录 ID/version，按明确显示条数确认整组删除；缺失任何身份或超过 50 条均拒绝。
- 前端校验不再静默过滤无效已有行；冻结提交快照、保存前加锁、失败保留草稿、版本冲突提供读取对照与显式合并。
- 结果未知时保留原请求键/正文；确认重试再收到 429/401 等也不能解除未知状态并产生新请求键。外层弹窗和内部导航共享锁，地图侧栏在切换标签时保留实例，避免销毁未确认请求。
- 三种语言提供保存、字段错误、冲突、未知结果、24 小时确认窗口和对照提示。日期仍按设备本地时区展示，无效日期显示 `-`。

## 数据结构迁移与上线依赖

新增 version、幂等回执表及索引；已有 informations 需要显式迁移为 AUTOINCREMENT，防止删除最大 ID 后新记录复用旧 ID，使过期草稿误操作新记录。

脚本 `scripts/migrate_user_custom_safety.py` 仅对显式传入的既有文件操作，不导入运行时数据库模块。默认/--check 为只读；--apply 才迁移。迁移在事务内复制原表，保留未知字段、显式索引和触发器，核对行数/最大 ID；遇到无法安全处理的 DDL 或外部引用则中止回滚，不静默丢弃结构。

发布流程：

1. 停写并备份 supplements.db，验证备份可恢复。
2. 执行只读检查，再显式迁移，再检查 ready 为 true。
3. 部署全部支持 ORM 版本递增的新后端；旧后端实例全部退出后恢复写入。
4. 部署前端。不得自动回退到删除后创建。保持旧协议期间，旧网页的两个 HTTP 请求仍无法由后端合并成事务，应促使刷新网页。

命令示例（由操作者替换数据库路径，不是本次已执行的命令）：

```bash
.venv/bin/python scripts/migrate_user_custom_safety.py --database /path/to/supplements.db --check
.venv/bin/python scripts/migrate_user_custom_safety.py --database /path/to/supplements.db --apply
.venv/bin/python scripts/migrate_user_custom_safety.py --database /path/to/supplements.db --check
```

回执有 24 小时确认窗口，单用户最多 200 条、全局最多 5,000 条，每条结果 JSON 最多 8 KiB。使用维护命令清理过期回执，每次最多 100 条；需要由既有维护安排按实际量调用，不新增常驻服务。容量满时拒绝新 save，不提前逐出有效回执。高于 100 条的过期积压需分次清理。

```bash
.venv/bin/python scripts/migrate_user_custom_safety.py --database /path/to/supplements.db --cleanup-receipts
```

**本次没有连接线上数据库，也没有对当前项目真实数据库执行迁移。** 新 ORM 依赖 version 列，不能跳过迁移直接发布后端。新增列和回执表不通过删表回滚；回退到不会递增版本的旧后端前必须停写并重新评估版本保护。

## 自动化验证结果

### 后端：129 项通过

隔离执行入口会在加载路由模块之前，把 supplements/auth/logs/vocabulary 的导入初始化指向临时目录。核心事务测试另外使用各自临时文件 SQLite，不使用当前真实 supplements.db。

```bash
.venv/bin/python scripts/run_user_custom_tests.py tests/test_user_custom_read_apis.py tests/test_user_custom_delete.py tests/test_admin_custom_identity.py tests/test_user_custom_mutations.py tests/test_user_custom_save.py tests/test_user_custom_versions.py tests/test_user_custom_routes.py tests/test_user_custom_legacy.py tests/test_user_custom_write_limits.py tests/test_orm_manager.py tests/test_cleanup_framework.py tests/test_search_custom_routes.py tests/test_auth_usage_reliability.py tests/test_admin_recent_trends.py tests/test_user_suggestions.py -q --disable-warnings
```

结果：129 passed；46 条依赖弃用警告。额外执行改动 Python 文件 compileall 和 git diff --check 均成功。

### 前端相关测试：47 项通过

```bash
npm run test -- tests/mapAdminBoundary.test.js tests/customDataApi.test.js tests/customDataModalSafety.test.js tests/customDataMutations.test.js tests/customDataPanelSave.test.js tests/customDataSaveState.test.js tests/customMapIdentity.test.js tests/customPopupDelete.test.js tests/pointDetailMutations.test.js tests/userDataMutations.test.js tests/customRegionTransport.test.js --maxWorkers=2 --silent
npx vite build
```

47 项通过，覆盖新 API 包装、校验、提交状态、用户页、地点与特征编辑、外层弹窗、地图侧栏、地图记录身份和弹出点删除，包含 Vue createApp/jsdom 组件测试。最终 `npx vite build` 成功（35.89 秒），保留既有 Node 模块 externalization 和大 chunk 提示；没有执行会改写 sitemap 的构建前置脚本。

前端全量 `vitest run --maxWorkers=2` 未通过，错误汇总期间触发 Node 堆内存耗尽。已修复本次新增 API 造成的 mapAdminBoundary 测试 mock 不匹配，相关 9 项重新通过。未将全量结果宣称为通过。

为核对其他失败，另在临时源码副本使用前端 HEAD，加上本次开始前已有且未修改的 AboutHistory.vue 工作区内容，复现下列 8 文件的相同 15 项失败；这不是新增的安全保存测试失败：

| 既有测试文件 | 基线失败数 |
| --- | --- |
| aboutFeatureTopology.test.js | 5 |
| aboutSuggestionForm.test.js | 1 |
| appFooterActions.test.js | 1 |
| featuresSectionSearch.test.js | 2 |
| globeJoystickContracts.test.js | 1 |
| historyTimeline.test.js | 3 |
| mapDrawEditorContracts.test.js | 1 |
| toponymCatalogEntrance.test.js | 1 |

前端新保存逻辑与主要编辑器的定向 ESLint 无错误和警告；MapLibre/MapData 等遗留文件仍有既有模板格式和未使用变量警告，不把全库 lint 宣称为通过。原有 sitemap、AboutHistory 和后端 search.py 改动未覆盖。

## 本地资源测量

```bash
.venv/bin/python scripts/benchmark_user_custom_mutations.py --matrix --iterations 10 --output docs/user-custom-safety-benchmark-2026-11-09.json
```

报告保存了 1/10/50 行 × 1/2/4 个竞争写请求 × 旧双提交模型/新事务接口的 18 组数据，包括 HTTP 延迟、并发读取探针、SQL 次数、BEGIN IMMEDIATE 等待、实际查询计划及整个基准进程峰值 RSS。数据库全部为一次性临时文件。

新接口并发门禁下出现 429 是明确的容量反馈，不能将拒绝请求后的较低延迟解释为吞吐提升。探针样本较少，旧流程是合成对照；RSS 为整个测试进程峰值，不是单请求/生产 worker 的内存。测试环境为 macOS ARM，**没有完成 2 核、2 GB 目标机器上的容量与在线 GET 延迟验收**，不能据此承诺生产性能。

## 尚未执行的环境验收

- 真实数据库备份恢复演练和显式迁移。
- 所有后端实例切换到版本递增代码、旧网页更新确认。
- 真实浏览器连接隔离后端的人工交互与移动端视觉验收；目前以组件测试、HTTP 路由测试和构建验证为证据。
- 目标机器基线对照与线上只读请求延迟测量。
- 历史导入时间是否全部按 UTC 保存的离线数据核查；旧时间字段和解释方式继续保留。
