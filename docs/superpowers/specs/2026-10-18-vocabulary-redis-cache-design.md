# 词表 Redis 缓存与主动预热方案

日期：2026-10-18。本文规定接口范围、缓存参数、失效事件和主动预热行为，尚未实施业务代码修改。

## 1. 已确认的范围

- 词表公开搜索、词表 SQL 数据查询接入 Redis。
- 固定默认查询主动预热且不设置 TTL；用户产生的其他查询缓存 3600 秒。
- entries 表提交了实际数据变更后，所有词表数据查询缓存失效，并主动重建全部默认缓存。
- locations 表单独发生实际变更时，特殊处理 map-points：仅其缓存失效，并主动重建默认 map-points。
- 删除地点、重命名地点、转移地点，以及管理员通用表格对 entries 的写入，都纳入统一通知。
- 不检测外部 SQLite 工具或独立脚本的写入。
- 前端上传成功后重新获取总词条数和地点数，解决当前页面只在挂载时读取计数的问题。

## 2. 当前实现与缺口

- `app/routes/vocabulary.py` 的五个 `/search/*` 接口当前直接查询数据库。
- `app/routes/vocabulary_sql.py` 的 count 和 columns 当前分别缓存 3600 秒，SQL query 和 distinct 接口无结果缓存。
- 上传、词表 SQL mutate、batch-mutate、batch-replace-execute 当前只删除 count 缓存，不主动预热。
- 地点删除、重命名、转移和管理员通用 SQL 写入当前未统一失效。
- `VocabularyViewPage.vue` 的卡片默认每页 50 条；地图标准词候选使用 `limit=1000`。
- `VocabularyImportPage.vue` 的两个计数只在挂载时获取，上传成功后未重新请求。
- Redis 只在 WEB 模式启用；MINE/EXE 模式继续直接查询数据库。

## 3. 明确的主动预热 API 清单

所有路径以 `/api/vocabulary` 为前缀。主动预热只覆盖下表中的固定组合，共七份结果；不会预热所有空 q 的筛选组合或所有分页。

| 编号 | 方法与 API | 固定参数 | 缓存有效期 |
| --- | --- | --- | --- |
| W1 | GET `/search/location-options` | 无参数，该接口没有 q | 不设 TTL |
| W2 | GET `/search/entries` | q 为空，无地点/省/市/标准词筛选，page=1，page_size=50 | 不设 TTL |
| W3 | GET `/search/map-points` | q 为空，无地点/省/市筛选 | 不设 TTL |
| W4 | GET `/search/standard-words` | q 为空，无地点/省/市筛选，limit=100（后端默认） | 不设 TTL |
| W5 | GET `/search/standard-words` | q 为空，无地点/省/市筛选，limit=1000（前端实际参数） | 不设 TTL |
| W6 | GET `/sql/query/count` | table_name=vocabulary_entries，无 filter，无 distinct_column | 不设 TTL |
| W7 | GET `/sql/query/count` | table_name=vocabulary_entries，distinct_column=location_name，无 filter | 不设 TTL |

W7 的含义是 `COUNT(DISTINCT location_name)`，只统计 entries 中的地点简称，不改成 locations 表行数，也不按 user_id 区分同名地点。

空 q 时，合法 search_fields 不影响结果，应规范化到同一默认缓存；非法字段依然先校验并返回原有错误。省略 q、空字符串 q、纯空白 q 使用一致语义。默认分页的省略写法与显式传入写法命中同一 key。

## 4. 只按需缓存、不主动预热的 API

| API | 行为 |
| --- | --- |
| `/search/entries` | 非 W2 的搜索、筛选、页码、page_size 组合缓存 3600 秒 |
| `/search/map-points` | 非 W3 的搜索、筛选组合缓存 3600 秒 |
| `/search/standard-words` | 非 W4/W5 的搜索、筛选、limit 组合缓存 3600 秒 |
| `/search/map-items` | 指定 standard_words 或 standard_word_key 的有效组合缓存 3600 秒；不预热所有标准词 |
| POST `/sql/query` | 完整查询参数对应的结果缓存 3600 秒，不预热所有表格组合 |
| GET `/sql/distinct/{table_name}/{column}` | 按表和列缓存 3600 秒 |
| POST `/sql/distinct-query` | 按目标列和有效筛选/搜索条件缓存 3600 秒 |
| GET `/sql/query/count` | 非 W6/W7 的筛选或 distinct 参数组合缓存 3600 秒 |
| GET `/sql/query/columns` | 保留结构缓存 3600 秒；普通数据变更不触发其清理或预热 |

`/locations`、`/me`、权限、日志、导出、导入预览、批量替换预览不增加结果缓存或主动预热。缓存命中不能绕过认证、权限、限流、参数校验和 page_size 限制。

## 5. 主动预热触发条件矩阵

变更通知必须发生在事务提交成功之后；失败回滚、纯查询和零实际变更不触发。

| 事件或入口 | 清理范围 | 主动预热范围 |
| --- | --- | --- |
| 应用启动 | 检查当前缓存版本和默认 key，不无条件清空有效结果 | 补齐缺失的 W1—W7 |
| POST `/imports` 上传或覆盖导入成功 | 全部词表数据查询缓存 | W1—W7 |
| POST `/sql/mutate` 实际新增、修改或删除 entries | 全部词表数据查询缓存 | W1—W7 |
| POST `/sql/batch-mutate` 至少提交一条实际变更 | 全部词表数据查询缓存 | W1—W7 |
| POST `/sql/batch-replace-execute` 实际修改 entries | 全部词表数据查询缓存 | W1—W7 |
| DELETE `/locations/{location_name}`，连带删除 entries | 全部词表数据查询缓存 | W1—W7 |
| PATCH `/locations/{location_name}`，重命名并实际更新 entries | 全部词表数据查询缓存 | W1—W7 |
| POST `/locations/transfer`，实际转移 entries 的 user_id | 全部词表数据查询缓存 | W1—W7 |
| 以上地点操作仅改 locations、没有实际改 entries | 仅 map-points 缓存 | W3 |
| PATCH `/locations/{location_name}`，仅改坐标、区域、调值、来源、描述等地点信息 | 仅 map-points 缓存 | W3 |
| 管理员通用表格 mutate、batch-mutate、batch-replace-execute 实际修改 vocabulary_entries | 全部词表数据查询缓存 | W1—W7 |
| 管理员通用表格上述入口仅实际修改 vocabulary_locations | 仅 map-points 缓存 | W3 |
| 一个事务同时修改 entries 和 locations | 全部词表数据查询缓存，一次通知 | W1—W7 |
| 权限、日志等其他表变更 | 不清理词表数据缓存 | 不预热 |
| 外部 SQLite 工具或独立脚本修改 | 不自动处理 | 不自动预热 |

对 entries 的转移即使没有改变总条数，也属于数据变更，不能因 count 不变而跳过通知。批量操作有部分成功并提交时，也按已提交的变更触发。地点更新传入的值与原值相同不触发。

## 6. locations 特殊处理的明确边界

本次按用户指定，仅 map-points 对 locations 独立变化立即刷新。

这意味着：location-options 中的省市和完整地点标签、entries 返回的地点标签、map-items 的地点信息，以及使用地点属性筛选的其他查询，仍可能保留旧结果。其中固定默认永久缓存等到下一次 entries 变更才刷新，其他按需缓存最多保留至 3600 秒过期。该边界是本次明确的刷新策略，不宣称所有依赖地点表的结果都立即更新。

不修改现有响应字段，不将地点元数据从搜索结果中拆除，也不扩大为 locations 更新时全接口失效。

## 7. Redis key 与读写策略

参考 `app/service/core/new_pho.py::generate_cache_key` 的 charlist 模式：固定字段参数对象，`json.dumps(sort_keys=True, ensure_ascii=False)`，对序列化结果取 MD5。复用设计方式，不修改 charlist。

建议 key 结构：

```text
vocabulary:default:data:<数据库标识>:<entries版本>:<接口类型>:<参数MD5>
vocabulary:default:map-points:<数据库标识>:<entries版本>:<locations版本>:<参数MD5>
vocabulary:ondemand:data:<数据库标识>:<entries版本>:<接口类型>:<参数MD5>
vocabulary:ondemand:map-points:<数据库标识>:<entries版本>:<locations版本>:<参数MD5>
```

数据库标识区分测试数据库和正式数据库；接口类型防止不同响应结构碰撞。版本使用不会在计数器丢失后重复使用旧命名空间的标识。参数键覆盖实际生效的 q、search_fields、locations、province、city、standard_words、standard_word_key、page、page_size、limit，以及 SQL filters、search_columns、sort_by、排序方向等字段。

只对语义无序的集合排序去重；影响排序或响应顺序的参数保留原序。SQL distinct-query 中不生效的自身目标列筛选与实际查询逻辑保持一致。不得对结果仍有区别的繁简字或参数进行未经验证的合并。

- W1—W7：Redis `SET` 不带 ex；即使由用户请求首次计算，也按永久缓存写入。
- 其他组合：Redis `SET ... EX 3600`。
- 先按有效参数判断是否属于 W1—W7，再选择 default 或 ondemand 命名空间。同一个默认组合不能因为由用户请求产生就写进 ondemand，也不能被限时写入覆盖而意外加上 TTL。
- 按需缓存容量达到上限时，先移除已过期的索引成员；仍满则淘汰最近最少使用的按需结果（LRU），再缓存新结果。这里是删除旧查询 key 并写入新查询 key，不能复用旧 key 存储不同查询结果。
- default 永久结果不登记进按需 LRU 索引，也不占按需名额。容量淘汰只能删除匹配当前数据库 ondemand 命名空间的 key，不能删除 default、其他模块缓存或控制用的版本/锁 key。数据变更失效仍可按既定事件范围清理 default 并主动重建。
- 成功的空结果、零计数也缓存；异常响应不缓存。
- 缓存未命中：直接查数据库并回填。
- 清理时先切换相应版本，使后续请求不再命中旧结果，再用 SCAN/UNLINK 清理旧版本 key；不使用生产全库 KEYS 扫描。
- 清理任务仅删除捕获到的旧版本命名空间，不能删除并发更新产生的新版本。
- 永久缓存的旧版本 key 必须清理，不能仅靠切版本而无限累积。

## 8. 预热执行与并发

1. 已提交的写入同步完成版本切换，再安排后台预热，不等待七个查询全部完成才返回写入响应。
2. 预热直接调用服务层查询，不通过 HTTP 回调自身，不额外消耗接口限流额度。
3. 多进程通过同一数据库的 Redis 全局预热锁选出一个执行者，跨版本也不并行预热；同一时刻最多执行一个预热查询，其余 worker 不重复启动查询。锁具有限时租约、续租和所有权校验，任务失败不能永久占锁。
4. 连续写入合并为最新版本的任务。只有 entries 变化需要 W1—W7；只有 locations 变化需要 W3；任务合并不能丢失更大的预热范围。
5. 预热、请求查询都绑定开始时的版本；旧任务不得把旧结果写入新版本 key。每份结果使用独立、可关闭的数据库 session，避免复用已经提交的请求事务或旧快照。
6. 预热期间用户请求访问新版本：通过同 key 分布式计算锁等待正在进行的计算，锁等待使用异步轮询、受限超时，不能用忙等或占用线程阻塞等待；未被预热计算的结果可按请求正常查库。不因普通锁竞争立即重复计算默认重查询，不返回旧版本结果。请求超时沿用服务的超时响应，不无限等待。
7. 默认缓存若被 Redis 淘汰或清除，后台缺失检查主动补齐，不只依赖首次访问。WEB 模式每 60 秒检查默认 key 是否缺失；健康检查本身不重跑已有查询。启动阶段同步补齐缺失结果后再就绪，多 worker 用锁协调。
8. Redis 异常时查询降级数据库，已成功的数据库写入不因后续缓存异常被描述为事务回滚。记录结构化失败日志并重试，首次恢复时先切换受影响版本、再补预热，不能重新使用失效失败前的旧 key。
9. 故障期间各查询绕过缓存；恢复后的版本同步及预热通过多进程锁协调。进程重启时检查初始化状态，不能把本地重试标记当成永久保障。

Redis 与 SQLite 不是同一事务。本次不承诺外部写入检测或跨进程崩溃时的数据库/Redis 原子提交；如需严格覆盖数据库提交后、版本切换前进程崩溃的窗口，需要另行引入持久化变更事件。常规路径和可恢复 Redis 异常必须覆盖。

### 8.1 2 核 2 GB 服务器的资源预算

生产资源约束优先于预热速度。七份缓存不是七个并发任务，也不等于占用七个 worker。

- 调度：一个可取消的串行后台协程，每次只把一个同步查询提交到现有线程池；不新建进程池，不增加 Web worker，不额外部署 Celery 等常驻服务。线程池内的查询仍消耗共享 CPU、内存和 I/O，不承诺零影响。
- 执行顺序：W6/W7 计数、W1 地点选项、W2 首屏、W3 地图点、W4/W5 标准词。相邻查询之间至少异步让出 100 毫秒。两个标准词结果共享一次 limit=1000 的聚合与排序，再截取前 100 个构造 W4，保留相同 total，避免同一版本全表聚合两次。
- 连续写入：第一次通知后等待 1 秒合并变化，最长 5 秒即启动；后台只保存最新版本和待执行范围，不为每次上传排一个完整任务。每份查询完成后检查版本，已过时则停止剩余旧任务，转向最新版本。正在执行的 SQLite 查询不能假定可以立即取消。
- 内存：逐项计算、序列化、写入、释放临时引用；不把全量 entries 或七份结果同时保存为 Python 对象，不在各 worker 中复制一套结果缓存。标准词聚合仍存在临时分组字典，这是需要测量的主要峰值之一，不能因最终只返回 1000 项而视为只有 1000 项内存。
- 按需缓存：3600 秒 TTL 只限制存活时间，不能限制高基数请求造成的内存增长。初始预算为该数据库全部词表按需结果合计最多 128 个 key，单结果序列化 UTF-8 大小最多 128 KiB，结果值合计理论上限 16 MiB，另有 key/索引/Redis 元数据开销。超过单项阈值正常返回但不缓存，且不为这个无法缓存的结果淘汰旧项；达到 key 数上限后按 LRU 淘汰旧按需结果、写入新结果。更新已存在的 key 不额外占名额，也不无故淘汰其他项。跨进程使用 Redis 有序集合维护最近使用顺序，缓存命中更新顺序但不延长 TTL；到期清理、淘汰和新项写入需由有界 Lua 脚本原子协调，不能用每 worker 本地计数或每次全库扫描。有序集合保持有界，容量统计跨所有接口和版本；版本失效清理同步移除对应成员。上述阈值支持配置。
- 永久缓存：只允许 W1—W7 固定组合，不允许把所有空 q 组合写成永久 key。记录每份结果字节数和总字节数，切版本后分批删除旧 key；删除和重建间存在的短暂副本也计入观测。不能把整个 Redis 的 maxmemory/淘汰策略改成词表专用策略，因为它还服务于其他模块。
- 重试：预热失败采用 5、15、60 秒间隔，后续最多每 60 秒尝试一次；与缺失检查共用同一个串行调度器和全局锁，不能生成并发重试任务。停服取消等待和后续调度，不强杀执行中的数据库线程。
- 验证：用实际词表记录冷预热总时长、各查询耗时、进程 RSS 峰值、Redis MEMORY USAGE、预热期间普通请求延迟和 SQLite 锁等待。测量须注明数据规模、并发和环境；开发机结果不能冒充生产 2 核 2 GB 结果。若出现 CPU 饱和、内存压力或在线延迟明显增加，先优化/分批重查询并增加让出间隔，不以增加 worker 掩盖问题。

本轮不调整服务器 worker 数、Redis 全局配置或其他模块的缓存。按需容量淘汰不改变 API 查询结果，淘汰项下次访问重新计算；超过单项体积上限只影响是否写入 Redis。

## 9. 预计修改位置

| 文件 | 责任 |
| --- | --- |
| 新增 `app/service/vocabulary/cache.py` | 参数规范化、key、版本、查询结果缓存、统一变更通知 |
| 新增 `app/service/vocabulary/cache_warmup.py` | 七份固定查询、任务合并、分布式锁、缺失补齐与失败重试 |
| `app/routes/vocabulary.py` | 五个搜索接口接入；地点写入区分 entries 与 locations 影响；上传统一通知 |
| `app/routes/vocabulary_sql.py` | 查询缓存；提交后的统一通知，替换散落的 count 清理 |
| `app/sql/sql_admin_routes.py` | 仅 db_key=vocabulary 且目标是 entries/locations 时通知，不影响其他数据库 |
| `app/lifecycle/startup.py`、生命周期后台服务与关闭入口 | 主服务启动预热及恢复检查；正确关闭任务；不在 GIS/cluster 服务重复启动 |
| `app/redis_client.py` | 如有需要补齐 Dummy 接口；非 WEB 模式不启动 Redis 预热 |
| 前端 `project/src/main/views/explore/word/vocabulary/VocabularyImportPage.vue` | 上传成功重新请求两个计数；遵守前端仓库规则且写入前取得所需目录权限 |
| `docs/api/vocabulary.md` | 说明 TTL、主动预热及 locations 特殊失效边界 |

## 10. 验收标准

- 默认七个 key 预热后 Redis TTL 为 -1；其他查询 key 的 TTL 不超过 3600 且为正数。
- 冷启动无需用户先访问即可得到 W1—W7；热启动不无条件重跑有效查询。
- 相同有效参数命中同一 key；不同分页、筛选、排序不串结果。
- 上传、单条、批量、批量替换、地点删除/重命名/转移、通用管理员写入后验证数据版本和主动预热。
- 对每个写入入口验证提交后触发、回滚不触发、无实际变化不触发；部分成功提交能触发。
- locations 单独更新验证旧 map-points 搜索与筛选缓存全部失效、W3 主动重建，其他缓存不受影响。
- entries 变化验证全部词表数据缓存失效；W1—W7 重建，按需组合下次请求回填。
- 并发查询和预热不会向新版本写入旧结果；连续写入最后生成最新版本默认结果。
- 跨 worker、跨版本预热并发查询数不超过 1；相同重查询缓存未命中不会因预热与请求同时到达而重复执行。
- 验证按需 key 达到上限后淘汰最近最少使用项、新项可命中、命中可改变淘汰顺序但不延长 TTL；更新已有 key 不额外淘汰，default 永久 key 的值及 TTL 均不受容量淘汰影响。
- 验证单项体积上限、过期名额释放、索引容量、跨版本统计和并发写入边界；记录实际默认缓存大小及预热内存峰值。
- 旧永久 key 被清理；Redis 缺失、超时、恢复可降级与补齐；MINE/EXE 模式行为不变。
- 缓存命中依旧执行认证和参数校验，不能绕过权限和请求上限。
- 前端上传成功后，无须重载页面即可重新获取两个计数；这不包含跨用户页面实时推送。

## 11. 实施顺序

1. 先实现与验证缓存 key、永久/限时写入、版本失效和旧 key 清理。
2. 接入公开搜索与 SQL 读接口，保持响应结构和校验行为。
3. 实现七份预热、启动补齐、锁与重试。
4. 统一所有受影响写入入口，验证 entries/locations 事件矩阵。
5. 修正前端上传计数刷新，更新接口文档，运行词表回归和新增缓存行为测试。

本轮交付为方案文档；实施时逐步检查 diff、验证并提交，不覆盖已有无关工作。
