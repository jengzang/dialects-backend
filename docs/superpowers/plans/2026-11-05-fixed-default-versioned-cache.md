# 固定默认请求的版本缓存 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 本计划顺序执行，无需新增 agent。

**Goal:** 根据前端实际请求，仅保留六份固定结果的跨 worker 版本缓存，取消 compare 的额外缓存及 feature_stats 结果缓存。

**Architecture:** 复用现有 Redis，六个固定槽位保存版本和完整响应；数据库版本变化才重算并覆盖，不使用时间过期。启动后主动串行预热缺失结果，不阻塞服务就绪；用户未命中时直接走原查询，不等待预热。复用现有线程卸载，不增加常驻服务或 worker。

**Tech Stack:** FastAPI、Python、SQLite、redis.asyncio、pytest；Vue 3、localStorage、Vitest。

---

## 1. 前端调用核实与范围

后端根目录：`/Users/jengzang/CodeProject/dialects/dialects-backend`。下文后端路径均相对此目录。
前端根目录：`/Users/jengzang/CodeProject/dialects/dialects-vue-frontend/project`。下文前端路径均相对此目录。

| 页面/用途 | 实际请求 | 触发条件 | 计划 |
| --- | --- | --- | --- |
| yubao 词汇候选全集 | `GET /api/yubao/vocabulary/words?all=true` | 进入页面，本地列表缓存未命中 | 固定版本缓存 |
| yubao 语法候选全集 | `GET /api/yubao/grammar/sentences?all=true` | 同上，两请求并发发出 | 固定版本缓存 |
| 首页、资料来源的已存地点数 | `GET /sql/query/count?db_key=query&table_name=dialects&filter_column=存儲標記&filter_value=1` | 浏览器对应版本未缓存或用户刷新 | 固定版本缓存 |
| 首页、资料来源的资料总数 | `GET /sql/query/count?db_key=dialects&table_name=dialects` | 同上 | 固定版本缓存 |
| villages N-gram 汇总 | `GET /api/villages/statistics/ngrams?type=gd` | NgramExplore 挂载；其他入口按按钮请求 | 固定版本缓存 |
| villages 信息页表信息 | `GET /api/villages/metadata/stats/tables?type=gd` | 信息页刷新表信息按钮 | 固定版本缓存 |

证据文件：

- 前端 `src/main/views/explore/word/YuBaoPage.vue:493`、`:518`、`:802`；`src/api/main/yubao.js`。挂载时调用两个全集入口；输入联想在本地过滤。空输入不会请求条目详情。选中条目后才请求 `/vocabulary/items?word=...&page=1&page_size=2000` 或 `/grammar/items?sentence=...&page=1&page_size=2000`，不为详情加缓存。
- 前端 `src/composables/data/useSourceStats.js:44`、`src/api/main/sql/query.js:105`。首页实际有两个 count，不是一个；`HomePage.vue` 和 `SourcePage.vue` 复用同一逻辑。
- 前端 `src/api/villagesML/metadata.js`、`src/api/villagesML/request.js`、`src/VillagesML/config/datasets.js`：请求包装器添加 `type=gd`，当前只有这一默认数据集。
- 前端 `src/VillagesML/workspace/modules/pattern/NgramExplore.vue:300`；`src/VillagesML/dashboard/Dashboard.vue:341`；`src/VillagesML/workspace/modules/system/SystemInfo.vue:459`。信息页挂载先读已有本地缓存，不因缺少表信息自动请求；按钮才强制发请求。Dashboard 挂载不主动加载 N-gram 汇总。
- 前端 `src/composables/data/useVillagesCache.js`、`src/utils/user/updateNoticeConfig.js`：首页与 villages 已有浏览器版本缓存；yubao 的两个 localStorage 键目前不带版本。

**信息页没有传 `table_name` 或其他 table 参数。** `/metadata/stats/tables` 返回整库表信息，包括行数估计、大小、索引、列等。不要为猜测的 table 组合创建缓存。

动态 N-gram 的 frequency、patterns、regional、tendency、significance 与汇总入口不同，不新增缓存；`/metadata/stats/overview` 也不新增缓存。其他业务已有缓存（包括 vocabulary、认证、限流等）不在本次调整范围。

## 2. 六份缓存的契约

### 固定白名单与版本

新增 `app/common/fixed_default_cache.py`，只承担这六份结果的版本校验、合并和存取，不替换全项目缓存框架。

| 固定 Redis 键 | 版本依赖 |
| --- | --- |
| `fixed_default:v1:yubao:vocabulary_all` | `DB_MAPPING['yubao']` |
| `fixed_default:v1:yubao:grammar_all` | `DB_MAPPING['yubao']` |
| `fixed_default:v1:sql:query_stored_count` | `DB_MAPPING['query']` |
| `fixed_default:v1:sql:dialects_count` | `DB_MAPPING['dialects']` |
| `fixed_default:v1:villages:gd:ngrams` | 默认 village 数据库 |
| `fixed_default:v1:villages:gd:tables` | 默认 village 数据库，含数据、索引和文件大小变化 |

- 使用固定键和 `{version, payload}` 值，新版本覆盖同一槽位；不是每次版本变化新增一个永久键。六份数据最多六个结果键。
- `version` 包含各槽位的响应/查询实现修订号，以及真实路径、DB 和 `-wal` 的 `(st_dev, st_ino, st_size, st_mtime_ns, st_ctime_ns)`。参考 `app/service/toponyms/execution.py::_version`，但基础 DB 不存在或 stat 异常必须旁路，不能把错误当成稳定版本；WAL 不存在是合法状态。
- 这是文件代次指纹，不是事务序号。正常写入、文件替换和建索引会失效；checkpoint 可能保守失效。禁止扫描或散列整个数据库，也不添加数据库版本表、触发器或迁移。刻意保留全部文件元信息的外部修改不在此机制保证范围内。
- 查询前后重新取版本，变化则不写缓存，不后台重试；本次返回按原查询语义得到的结果，下次请求重算。缓存命中也复核版本，减少读取期间变更的窗口；不承诺对并发写入提供超出现有 SQLite 事务语义的快照保证。
- 不设置 TTL；普通部署、worker 回收、前端刷新不主动清除。查询实现改变时只提升受影响槽位修订号。
- Redis 重启、淘汰或故障仍可能丢缓存。不改生产 Redis 持久化、maxmemory、淘汰策略；“无 TTL”不能等同于永久可靠存储。

### 参数与权限

- yubao 仅 `all=true` 且没有有效筛选的全集路径使用固定槽位。`q=None` 或空字符串遵循当前实现；不能通过 `.strip()` 把有意义的空白搜索误归为全集。`limit` 在现有 all 模式下被忽略，保持原语义。
- SQL 只匹配上表两个规范化后的精确参数组合；禁止让额外条件、其他库表或权限别名误命中。按路由已解析的值比较，不自行扩大字符串/数值等价范围。
- villages 仅当前默认 gd/village 数据库命中。当前后端通过默认 `dbpath=village` 解析数据库，`type=gd` 不能被当成已经实现多数据集路由；显式其他 dbpath 不命中。缓存键不能包含 sqlite 连接、Session、Request 或其对象 repr。
- 认证、权限检查、库表/列名校验、限流都在缓存读取前执行。尤其 SQL 当前部分权限检查位于连接入口，不能因为命中缓存跳过它。
- 响应字段、排序、状态码和数值类型保持兼容；不缓存异常、权限失败、查询超时。合法空列表和 count=0 可以缓存。

### 2 核 2 GB 的资源边界

- 只存 Redis，不为每个 worker 再维护结果常驻副本。初始设计上限为每槽序列化 UTF-8 payload 1 MiB、六槽总 payload 6 MiB；这些是设计阈值，**不是实测 Redis/RSS 占用**。超限返回完整原响应，跳过缓存，不截断数据。实现阶段测量六个真实响应；若任一超限，先报告数据大小再决定是否调整阈值。
- **启动主动预热**：在 `app/main.py::_build_lifespan` 安排有限后台任务后立即进入 `yield`，不等待六份计算完成。每次启动先检查版本，有效槽位跳过，不清空缓存。
- **后台只有一份**：主机级 flock 选出一个预热执行者，其他 worker 跳过；六项逐项执行，同时最多一个本计划的后台查询。参考 `app/service/toponyms/resources.py::_slot` 使用独立固定锁文件，不更改 toponyms 调度。
- **请求不等预热**：缓存未命中、版本失效或 Redis 故障时，检查权限后直接走原查库路径，不等待预热、不进入预热名额、不因预热新增 503。不新增请求合并等待队列。按用户要求接受预热和前台可能重复计算的成本。
- 前台计算成功后可非阻塞尝试取得发布锁并复核版本后写缓存；预热持锁时跳过该次写入，立即返回完整响应。后台每项开始前重新读缓存，跳过前台已完成项。禁止旧版本覆盖新版本。
- 复用现有线程卸载，不新建 executor；同步文件检查、锁操作、序列化和 SQL 不在事件循环执行。后台名额在实际 SQL 停止后释放，不能仅取消 asyncio 包装任务；锁文件不 unlink，进程退出自动释放 flock。
- 预热使用可中断的独立只读连接，SQLite progress handler 限制每项执行预算 30s，整轮预算 120s；这是设计上限，不是实测耗时。多语句 loader 在语句间检查期限；超时中断后关闭连接。不向共享池连接遗留 handler，不改数据库持久配置。
- Redis 不可用则结束本轮预热，不继续查询六项。单项失败或超限不缓存，按总预算继续下一项；无定时循环、无失败自动重试。后续请求仍能回源填充，下次启动再次检查。运行期间数据版本变化由请求发现，不新增常驻轮询。
- Shutdown 先通知停止并中断在途预热 SQL，实际计算退出后再关闭连接池/Redis。每个 app profile 只预热自身提供的接口，不让 GIS 进程为预热导入整套主应用服务。
- **资源边界**：后台最多增加一个查询，不限制原有在线查询总并发；前台可与预热同时查库，不能承诺总内存或 I/O 不增加。需测量与已有 vocabulary 预热叠加的影响；若负载过高，优先让两套启动预热串行，不增加 worker/线程。

## 3. 顺序实施任务

### Task 1：锁定行为与缓存基础

**Create:** `app/common/fixed_default_cache.py`、`tests/test_fixed_default_cache.py`。

- [ ] 先写失败测试：同版本先填充后连续请求 loader 次数为 1；模拟第二个 worker 读同一 Redis 结果不执行 loader；修改 DB/WAL 指纹后次数变为 2，Redis 结果键仍为 1。
- [ ] 覆盖 WAL 创建/移除、DB 替换、stat 错误、计算中版本改变、合法 0/空列表、非法 JSON/旧 envelope、Redis get/set 失败和超限不缓存。全部使用临时 SQLite 与 fake Redis，不连接生产。
- [ ] 实现上节契约；固定槽位用枚举/常量注册，调用方不得传入任意结果键。异步入口接收槽位、数据库真实路径、同步 loader 和实现修订号，返回原 payload；前台 miss 直接执行 loader，发布锁只能非阻塞取得。
- [ ] 加两进程 flock 测试：后台预热同时最多一个 loader；预热持锁时前台仍能开始查询并返回；实际后台 SQL 未停止前不能释放名额。
- [ ] 运行 `python -m pytest tests/test_fixed_default_cache.py -q`，先确认失败原因属于新能力缺失，实现后全部通过。提交本任务涉及的明确文件。

### Task 1A：启动自动预热（在 Task 2–4 提供 loader 后完成集成）

**Create:** `app/lifecycle/fixed_cache_warmup.py`、`tests/test_fixed_cache_warmup.py`。
**Modify:** `app/main.py`。

- [ ] 先测试不发 HTTP 请求也启动预热；六槽有效则不查库；缺失项顺序执行；多个 worker 同时启动只有一份后台查询。
- [ ] lifespan 完成基础初始化后安排任务，不等待全轮完成；调用与路由共享的同步 loader，不通过需要用户凭证的 HTTP 接口预热。
- [ ] 测试阻塞后台 loader 后发起同端点请求，前台 loader 必须开始且可先返回；解除阻塞后核对缓存版本和响应一致。
- [ ] 覆盖 Redis 故障终止、单项失败继续、查询中版本改变、SQL 超时中断、shutdown、GIS profile；检查已有 vocabulary 预热的资源叠加，必要时串行。
- [ ] 运行 `python -m pytest tests/test_fixed_cache_warmup.py tests/test_fixed_default_cache.py -q`，通过后提交新增文件及 lifespan 改动。

### Task 2：yubao 两个全集与前端版本兼容

**Modify:** `app/routes/yubao.py`、`app/service/yubao/service.py`；必要时 `app/service/yubao/repository.py`。
**Test:** `tests/test_yubao_routes.py`、`tests/test_yubao_thread_offload.py`，新增 `tests/test_yubao_fixed_cache.py`。
**Frontend Modify:** `src/main/views/explore/word/YuBaoPage.vue`。
**Frontend Create:** `tests/yubaoCacheVersion.test.js`。

- [ ] 先测试两条 all 请求复用各自唯一结果槽；q 筛选、非 all 请求、items 详情不读写这两个槽；响应与未缓存版本一致。
- [ ] 将两个列表入口接入 helper，保留线程卸载。仅无筛选全集允许用 `len(items)` 替代重复 COUNT，验证 DISTINCT、NULL、空白过滤后的 total 一致；筛选和分页计数不改。
- [ ] 前端复用已有 `getHomeUpdateNotice(...).dbVersion` 作为两个 yubao 本地键的版本后缀，忽略旧无版本列表；测试相同版本复用、版本变化重拉两列表、输入联想不发列表请求、空输入不发详情请求。保持 UI 和接口参数不变。
- [ ] 发布说明明确：后端指纹变化不会主动推送到浏览器。数据发布时同步提升已有前端 dbVersion，才能让已打开过页面的浏览器在新版本重新拉列表；不声称后端版本自动清除 localStorage。现有首页/villages 使用同一发布约定。
- [ ] 后端运行 `python -m pytest tests/test_yubao_routes.py tests/test_yubao_thread_offload.py tests/test_yubao_fixed_cache.py -q`；前端根目录运行 `npm test -- tests/yubaoCacheVersion.test.js`，不安装依赖。确认通过后分别提交两个仓库的指定文件。

### Task 3：首页两个 count 改成版本缓存

**Modify:** `app/sql/sql_routes.py`。
**Create:** `tests/test_sql_fixed_count_cache.py`。
**Existing tests:** `tests/test_sql_routes_thread_offload.py`、`tests/test_sql_admin_permissions.py`。

- [ ] 先覆盖两个固定请求命中/版本变化；其他表、筛选值、列名或额外条件都不使用固定缓存。命中与未命中均测试权限不足返回原错误。
- [ ] 去掉此模块 `/query/count` 的任意参数 TTL 缓存，以及 `/query` 旧的广泛 total 缓存写入；仅上表两个默认 `/query/count` 使用固定 helper。其他查询正常计算，不扩展新的缓存组合。
- [ ] 把缓存前必须执行的权限检查从连接副作用中明确出来；保留 DB 路径解析、过滤 SQL 参数化、线程卸载和响应 `{count: ...}`。
- [ ] 运行 `python -m pytest tests/test_sql_fixed_count_cache.py tests/test_sql_routes_thread_offload.py tests/test_sql_admin_permissions.py -q`，对两条 count 和动态筛选响应做无缓存基准对照；通过后提交。

### Task 4：villages 两个汇总结果改成版本缓存

**Modify:** `app/villagesML/statistics/__init__.py`、`app/villagesML/metadata/stats.py`；需要调整连接持有范围时修改 `app/villagesML/dependencies.py`。
**Create:** `tests/test_villagesml_fixed_cache.py`。
**Existing tests:** `tests/test_villagesml_schema_runtime.py`；前端 `tests/villagesMLCacheKeys.test.js`。

- [ ] 测试默认 gd/village 的完整 N-gram 汇总和完整 tables 响应；同版本跨连接命中，其他 dbpath 不命中；建索引/修改数据使 tables 失效。
- [ ] 去掉两处 `@api_cache(ttl=300, ...)`，接入固定槽位；不扩展/重写通用 `cache_utils.py`。动态接口与 overview 不新增缓存。
- [ ] N-gram 数据库连接改成冷 loader 内获取及 finally 关闭，命中时不为了依赖注入创建连接；保留原路径校验和合法数据集行为。tables 使用现有同步查询，不新增长期连接。
- [ ] 验证 SystemInfo 无表参数、挂载仅读已有列表、按钮 forceRefresh 只绕过浏览器缓存的行为保持不变；不添加后端强制清缓存参数。
- [ ] 运行 `python -m pytest tests/test_villagesml_fixed_cache.py tests/test_villagesml_schema_runtime.py -q`；前端运行 `npm test -- tests/villagesMLCacheKeys.test.js`；通过后提交。

### Task 5：取消 compare 和 feature_stats 的结果缓存

**Modify:** `app/routes/core/compare.py`、`app/routes/core/phonology.py`。
**Create:** `tests/test_core_cache_policy.py`。

- [ ] 先测试 `/compare/ZhongGu` 重复请求：`charlist:*` 仍可复用；统计和地点结果每次走原计算；不读写 `compare_zhonggu_stats:*`、`compare_zhonggu_locations:*`。
- [ ] 删除 `_resolve_stats` 与 `_resolve_locations` 的额外 get/set/键生成，保持 `_resolve_chars` 的 charlist 缓存与 600s 策略。此处按用户“只保留复用 charlist”处理，地点结果缓存也取消。
- [ ] 测试 `/feature_stats` 连续相同请求均执行原统计，不触碰其结果 Redis 键；删该路由结果缓存逻辑，保留权限、响应、异常处理和线程卸载。检查 import 真实使用情况后清理，其他路由缓存不改。
- [ ] 运行 `python -m pytest tests/test_core_cache_policy.py -q`，覆盖正常和异常响应；旧 TTL 键让其自然过期，不在生产做 SCAN/批量删除。通过后提交。

### Task 6：避免普通清理删除版本结果

**Modify:** `app/service/admin/system/cache.py`。
**Create:** `tests/test_fixed_cache_clear_policy.py`。

- [ ] 为 `clear_redis_cache_logic` 和 `clear_all_cache_logic` 写测试：普通 `*` 清理保留 `fixed_default:v1:*`，仍删除其他匹配缓存，返回删除数与保留数；bytes/string 键均正确识别。
- [ ] 两个入口使用同一个命名空间保护规则。SCAN 分批处理，删除批次上限 100，不累积全 Redis 键列表；不使用 FLUSHDB。普通管理员指定 pattern 也不绕过保护；不新增任意清除固定缓存的 API。
- [ ] 版本结果损坏按读取失败重建；查询实现修正通过槽位修订号失效。前端刷新不连接清理入口。
- [ ] 运行 `python -m pytest tests/test_fixed_cache_clear_policy.py -q`，通过后提交。

### Task 7：本地验证实际收益与交付

**Create:** `scripts/benchmark_fixed_default_cache.py`、`docs/fixed-default-cache-validation-2026-11-05.md`。

- [ ] 基准脚本仅接受显式本地路径，默认单请求串行执行；不连接服务器、不复制生产数据库、不运行写入型迁移。不提供无限循环/无界并发选项。
- [ ] 对六份真实本地响应分别测未缓存、首次构建、同版本命中、版本变更、Redis 故障；记录响应字节数、SQL 次数、耗时、进程峰值 RSS 和 Redis MEMORY USAGE。冷/热区分，串行各 5 次，报告中位数和范围，不预先承诺毫秒或 MiB 收益。
- [ ] 用临时小数据库做 2 个进程、每进程最多 4 个请求的短并发检查，确认后台构建峰值为 1、前台不等待预热、无后台遗留计算；混合普通轻请求检查事件循环响应。Redis 不可用时验证预热结束、前台照常查库且无自动重试风暴。
- [ ] 重点报告取消 compare/feature_stats 结果缓存后的 SQL/CPU 成本，不能只列新增缓存的好处。同时报告预热与在线请求重叠时的峰值 RSS、I/O 和延迟。预热预算不足时记录未完成槽位，不让前台等待或扩大后台并发来掩盖问题。
- [ ] 运行上述新增与相关现有测试的合并集合；前端跑两个指定缓存测试和受改文件 lint。记录环境、命令、基线失败及不具备真实本地数据的测量项，不用合成数据冒充实际收益。
- [ ] 检查 `git diff --check`、两仓库 diff 与状态；只提交本任务文件，保留 `app/lifecycle/db_backup.py` 和其他已有改动。提交验证报告及脚本。

## 4. 最终验收与不涉及事项

- 六个默认结果跨 worker 复用、按数据库版本替换；不因时间、页面刷新或普通清理过期。key 数不会随请求参数或版本数增长。
- compare 仅保留 charlist 复用；feature_stats 不再缓存统计结果。
- SQL 动态总数不新增/保留本模块的泛化 TTL 缓存；动态 yubao/N-gram 不新增缓存；现有其他子系统不扩范围。
- 所有默认响应与原逻辑一致，权限检查先于命中；故障/超限不缓存错误、不截断响应；后台预热并发与执行预算有界，前台未命中不等预热、不新增重试。
- 前端只做 yubao 已有本地缓存的版本兼容，不调整展示、地图、详情或分页；明确浏览器更新依赖既有发布版本约定。
- 不改服务器配置、连接池、SQLite page cache、ORM 配置，不增加索引，不启动服务，不部署。本计划完成后再按任务实施和测量。
