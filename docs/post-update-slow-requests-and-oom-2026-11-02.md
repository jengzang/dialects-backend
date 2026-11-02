# 更新后慢请求与 OOM 复查

调查时间：2026-11-02 23:35～23:43，北京时间。只读 SSH、读取日志和源码、SQLite 只读 SELECT；没有修改服务器配置、业务数据、代码或服务，没有运行查询复现、压测和分析任务。聚合在本地完成。

## 结论

1. 本轮更新确实在运行：容器启动于 **11-01 17:54:31**，连接池、vocabulary query/literal_scan/scope_plan，以及 startup/logging database 源文件哈希与本地一致。
2. vocabulary 常见查询有变快迹象，但尾部慢请求仍存在，最慢全域 `entries?q=哈欠` 为 **13.269 秒**。
3. **整机 OOM 尚未缓解**：部署前后各 24 小时均为 **8 次**；更新后至本次采集共有 **11 次内核确认的 global OOM**，另有一次启动阶段的 **300 秒 worker timeout**。不能把两类 SIGKILL 混算。
4. 最新几次 OOM 的证据更支持“三个 worker 的较大存量工作集，加上宿主进程/内核占用，内存回收余量不足”，无法归罪于某一个 vocabulary 请求。后述最新五次的前后两分钟均未见 vocabulary 请求完成记录。

## 时间、范围与取证成本

- 部署分界：11-01 17:54:31。部署前 24 小时为 10-31 17:54:31～11-01 17:54:31；部署后第一天截止 11-02 17:54:31。
- `auth.db/api_usage_logs`：仅检查主键最近 30000 条中的 10-31 起记录，返回 2043 条。独立只读连接缓存 512 KiB，查询约 0.121 秒。
- `logs.db/api_diagnostic_events`：时间索引限定同一范围，返回 108 条，约 0.025 秒。取证 Python 峰值 RSS 约 12.3 MiB。两张表串行读取，不持有长事务。
- Nginx 最后 20000 行中筛取 API/admin 等请求，下载 5561 行、约 2 MiB，覆盖 10-31 16:46:39 至本次采集。
- auth 时间为请求开始的 UTC；diagnostic occurred_at 为记录事件时的 UTC；Nginx 是响应结束的北京时间。本报告请求表统一换算为北京时间开始时间。
- 参数匹配依据：来源 IP、路径、状态、auth 开始时间＋duration 与 Nginx 完成时间；同类临近记录选择最近者。两条 >10 秒查询另有 diagnostic 完整参数佐证。现有记录没有统一 request ID / worker PID，不能将某个 HTTP 请求绑定到被杀 worker。

## vocabulary 慢请求

下表均发生在更新后，均返回 200。字段 `definition` 为标准词、`headword` 为方言词。列出的全域请求没有 locations、省市或分区过滤。

| 请求开始（北京） | 端点 `/api/vocabulary/…` | 秒 | 请求条件 |
|---|---|---:|---|
| 11-02 23:22:26 | search/entries | 13.269 | q=哈欠；search_fields=definition,headword；page=1；page_size=50 |
| 11-01 21:28:23 | search/entries | 11.247 | q=呷；search_fields=definition,headword；page=1；page_size=50 |
| 11-01 20:00:56 | search/entries | 9.557 | q=刀豆；search_fields=definition；page=1；page_size=50 |
| 11-02 03:32:11 | search/entries | 9.418 | q=岳父；search_fields=headword,definition；page=1；page_size=50 |
| 11-02 20:22:24 | search/entries | 9.332 | q=中午；search_fields=headword,definition；page=1；page_size=50 |
| 11-02 20:22:42 | search/standard-words | 8.025 | q=中午；search_fields=headword,definition；limit=1000 |
| 11-02 23:22:32 | search/map-points | 7.502 | q=哈欠；search_fields=definition,headword |
| 11-01 21:02:09 | search/standard-words | 3.306 | 无 q、无 locations；search_fields=definition,headword；region_mode=yindian；limit=1000 |

超过 1 秒的 vocabulary 请求共 20 次，超过 3 秒的共 10 次，其中包含两次导入。完整 20 条及参数见文末列表。

其他慢调用：

- `POST /api/vocabulary/imports`：11-01 18:06:26 为 2.486 秒、21:01:58 为 5.365 秒、21:57:25 为 8.499 秒。
- `POST /api/vocabulary/sql/query`：11-01 21:58:59 为 2.070 秒、11-02 01:18:54 为 2.627 秒。
- `POST /api/ZhongGu`：11-02 15:17:41 / 15:17:59 / 15:18:24 为 7.659 / 4.217 / 6.414 秒。
- `POST /api/tools/praat/uploads`：更新后 60 次超过 1 秒，其中 4 次超过 3 秒，最大 3.615 秒。上传耗时还包含文件传输，不能与数据库查询等同。

上述 POST 在所查持久化记录中没有对应可还原正文；Nginx 也不记录正文。本次无法给出导入文件、SQL 条件或 ZhongGu 字表的准确内容，不以猜测补齐。全部 >1 秒请求的时间、耗时、状态和可恢复 URL 已保存为本地 CSV。

### 更新前后怎么比较

`search/entries`：部署前 24 小时 23 次，中位耗时 **2.793 秒**，10 次 >3 秒；部署后约 30 小时 38 次，中位耗时 **0.170 秒**，5 次 >3 秒，但最大值仍为 13.269 秒。

样本的关键词、缓存冷热和并发不一致，因此不能据此给出因果提速倍数。`location-options`、`partition-options` 更新后最大约 0.153/0.130 秒；`map-items` 最大约 0.241 秒。问题集中在少量全域内容搜索、全域聚合及导入，而非所有 vocabulary API 普遍很慢。

### 剩余慢路径与解释边界

- 线上数据库文件约 133 MiB；sqlite_stat1 中 vocabulary_entries 统计基数为 **514811**，这是 ANALYZE 统计而非本次重新 COUNT 的实时总数。不能再按本地 95003 行小库的速度推断生产表现，也不能把统计基数当精确当前行数。
- “呷”是单字，不满足本轮字面预过滤条件；全域 LIKE 仍可能扫描。`definition` 单字段保留覆盖索引计数路径，不能套用两字段短页推断的收益。
- “哈欠/岳父/中午”虽为多字，也不保证索引子串定位；新增预过滤和有界规划减少部分工作，没有把所有全域子串查询变成索引查找。
- `standard-words` 无 q 的调用仍需跨组归一聚合。`limit=1000` 限制最终输出，并不限制中间分组总数。
- 缓存未命中时，请求耗时可能包含资源准入、SQLite 读取、Python 处理、Redis 与响应编码。现有日志没有这些阶段耗时，不能把 13.269 秒全部归因于 SQL 或断言某次一定缓存未命中。

## OOM 是否改善

| 观察窗口 | 内核确认 global OOM |
|---|---:|
| 部署前 24 小时 | 8 |
| 部署后第一段 24 小时 | 8 |
| 部署后至本次采集，约 29.8 小时 | 11 |

没有观察到 OOM 频率下降。该比较未控制宿主后台任务和在线工作量，不证明修复本身导致恶化；它说明确定的连接池缺陷修好后，整机容量问题仍存在。

所有 11 次均有 `constraint=CONSTRAINT_NONE,global_oom`、明确 victim PID 和 `Out of memory: Killed process`，与 Gunicorn SIGKILL/补起 worker 对应。配置仍为 3 worker、max_requests=5000、jitter=200；这些事件不是达到请求次数后的正常退出。

### 最新五次 kill

RSS 是内核实际驻留页统计，不是 total-vm。RSS 汇总可能重复计算共享页，不能直接当作 PSS 或唯一物理占用。

| OOM 时间（11-02，北京） | 宿主 victim / 容器 worker PID | victim RSS MiB | 邻近请求与判断 |
|---|---|---:|---|
| 15:23:29 | 2874725 / 2536 | 516.3 | 15:23:11 phonology_matrix(locations=張家港楊舍) 已200，耗时0.250秒；15:23:30 locations/detail(name=張家港楊舍) 返回200。分配触发者是宿主 python3.7；无证据证明音系请求单独引爆内存。 |
| 17:17:35 | 2877655 / 3043 | 455.2 | 17:16:43 Praat uploads/jobs、17:16:46 result?view=full 已200，距离 OOM 约49秒。宿主 python3.7 触发；只能列为历史负载关联，不能证明 Praat 导致此 kill。 |
| 20:08:46 | 2882211 / 3749 | 429.6 | 20:07:06 Praat uploads/jobs、20:07:07 result 已200；前30秒没有所采集 API 完成。AliYunDunUpdate 触发。20:08:59 的新上传在 OOM 之后，不能倒因为果。 |
| 22:08:48 | 2881436 / 3519 | 453.0 | 前120秒没有所采集 API 完成记录；AliYunDunUpdate 触发。更支持存量内存压力，不支持归因于临近 vocabulary 请求。 |
| 23:33:52 | 2884495 / 4039 | 459.7 | 前120秒仅见在线时长上报及23:33:49 auth/refresh 完成。23:33:54 admin/api-usage 列表返回200（limit=50、include_stats=true）；缺其开始时间，不能证明它在 kill 后才开始，也不能认定它为原因。触发者仍是 AliYunDunUpdate。 |

“前窗口没有完成记录”不等于没有未完成请求或后台任务。没有 worker 级 request ID，无法还原死进程当时的 Python 栈。

### 系统层原因的直接证据

- 上述最近五次，3 个 worker 的 RSS 合计约 **1241～1278 MiB**，master 另约80 MiB；宿主 python3.7 进程合计约 **89～125 MiB**。宿主这些进程为 UID0 / Python3.7，与容器 UID1000 / Python3.12 不同；具体历史命令未留存，不能进一步指定为某个脚本。
- 最近一次内核记录 active_anon＋inactive_anon 约 **1.48 GiB**，另有文件页、slab、页表、系统服务等；DMA32 空闲约46 MiB，接近其 min watermark 约44 MiB。整机分配/回收余量很小。
- 宿主 `vm.swappiness=0`，容器 `memory.swappiness=0`。OOM 快照中的 gunicorn swapents 都为0，而宿主仍有约1.82 GiB空闲swap。swap存在但没有为这些 worker 工作集提供实际缓冲；不能将“还有swap”视为不会 OOM。本次没有修改该设置。
- 容器 memory limit 为 **1536 MiB**，采样 max_usage 约 **1380.7 MiB**、failcnt=0；结合 global_oom，证据不支持“触碰容器硬上限后被杀”。不要把提高该上限当作本轮根因修复。
- `AliYunDunUpdate invoked oom-killer` 只说明谁的页分配首先失败。其自身不是日志中最大的内存使用者，不能将全部责任归到阿里云安全进程。

因此本次能确定的系统原因是：**整机内存余量不足，较大的多 worker 工作集持续存在，宿主后台分配会触发 global OOM，内核选择较大的 gunicorn 杀死。** 哪些 Python 对象/SQLite 页缓存占了多少、各 worker 如何涨到该水平，现有快照无法分摊；连接池缺陷修复也不等于已有每连接缓存目标或全部常驻对象已经缩小。

## 启动阶段那次 timeout

11-01 17:54:43 worker16 被 fork；worker17/18 在17:54:57完成初始化，但未见 worker16 的 initialized/Started server process 记录。17:59:43 出现 WORKER TIMEOUT，17:59:44 SIGKILL。该时段无内核 OOM。

这更像 worker16 在初始化/导入阶段卡住，现有证据不足以定位具体函数或证明死锁。master 在 fork 前已启动日志线程、scheduler 和清理线程，属于后续值得离线检查的生命周期点；不能据此直接断言多线程 fork 是此次根因，也不应先通过调大 timeout 掩盖。

## 后续优化顺序（未实施）

1. **先处理存量工作集。** 在本地按现有3 worker和2C2G约束测量启动、预热、词表查询、音系/Praat后的PSS及连接数。现有 startup 预建23条原生连接，日志迁移还会创建默认10条池；每连接原生 cache_size=-16000、日志ORM=-64000仍在。它们是缓存目标而非预分配/硬上限，不能把乘积当实际用量；需要分项测量后缩减池和缓存预算。
2. **对上表真实查询离线复测。** 优先“哈欠/呷/刀豆/中午”，区分 count、page、聚合、Redis、资源等待与编码，并使用与线上统计基数相近的数据。单字、全域扫描和全域分组须单独验收；不能只增加线程/worker。
3. **补足低成本归因。** 若后续授权实施，记录request ID、worker PID、查询阶段耗时和抽样内存；采样需有频率/输出上限，不记录上传二进制。这样下一次才能分清空闲存量、某条查询峰值或后台任务。
4. **资源配置只做受控验证。** swappiness、worker数量、缓存预算都存在吞吐/尾延迟/I/O权衡；不承诺一个参数即可解决，也不在本次生产环境修改。

## 本地证据

目录 `outputs/post-update-20261102/` 已被 Git 忽略，包含原始内核日志、worker事件、部署哈希、只读数据库结果、Nginx样本、`slow-requests.csv`、`oom-events.json` 和本地分析脚本。最终23:43:30复核，23:35之后没有新增内核 OOM 记录。

## 附：全部 20 条超过 1 秒的 vocabulary 请求

POST URL 没有正文参数，表内明确标记；GET 参数经 URL 解码。

| 请求开始（北京） | 秒 | URL / 参数 |
|---|---:|---|
| 11-01 18:06:26 | 2.486 | /api/vocabulary/imports（POST；正文未还原） |
| 11-01 20:00:56 | 9.557 | /api/vocabulary/search/entries?q=刀豆&search_fields=definition&page=1&page_size=50 |
| 11-01 21:01:58 | 5.365 | /api/vocabulary/imports（POST；正文未还原） |
| 11-01 21:02:09 | 3.306 | /api/vocabulary/search/standard-words?search_fields=definition,headword&region_mode=yindian&limit=1000 |
| 11-01 21:28:23 | 11.247 | /api/vocabulary/search/entries?q=呷&search_fields=definition,headword&page=1&page_size=50 |
| 11-01 21:57:25 | 8.499 | /api/vocabulary/imports（POST；正文未还原） |
| 11-01 21:58:17 | 2.756 | /api/vocabulary/search/entries?search_fields=definition,headword&locations=東莞沙田話&region_mode=yindian&page=1&page_size=50 |
| 11-01 21:58:59 | 2.070 | /api/vocabulary/sql/query（POST；正文未还原） |
| 11-02 01:18:54 | 2.627 | /api/vocabulary/sql/query（POST；正文未还原） |
| 11-02 03:32:11 | 9.418 | /api/vocabulary/search/entries?q=岳父&search_fields=headword,definition&page=1&page_size=50 |
| 11-02 03:32:33 | 1.491 | /api/vocabulary/search/entries?q=岳父&search_fields=headword,definition&locations=花蓮壽豐五雲客家話&page=1&page_size=50 |
| 11-02 20:16:39 | 2.816 | /api/vocabulary/search/entries?q=君不见黄河之水天上来&search_fields=definition,headword&locations=五華水寨話(下側聲)&page=1&page_size=50 |
| 11-02 20:16:48 | 2.489 | /api/vocabulary/search/entries?q=君&search_fields=definition,headword&locations=五華水寨話(下側聲)&page=1&page_size=50 |
| 11-02 20:16:57 | 2.769 | /api/vocabulary/search/entries?search_fields=definition,headword&locations=五華水寨話(下側聲)&page=1&page_size=50 |
| 11-02 20:22:24 | 9.332 | /api/vocabulary/search/entries?q=中午&search_fields=headword,definition&page=1&page_size=50 |
| 11-02 20:22:42 | 8.025 | /api/vocabulary/search/standard-words?q=中午&search_fields=headword,definition&limit=1000 |
| 11-02 20:46:26 | 2.759 | /api/vocabulary/search/entries?q=还&search_fields=definition,headword&locations=五華水寨話(下側聲)&page=1&page_size=50 |
| 11-02 23:22:26 | 13.269 | /api/vocabulary/search/entries?q=哈欠&search_fields=definition,headword&page=1&page_size=50 |
| 11-02 23:22:32 | 7.502 | /api/vocabulary/search/map-points?q=哈欠&search_fields=definition,headword |
| 11-02 23:22:46 | 2.491 | /api/vocabulary/search/entries?q=哈欠&search_fields=definition,headword&locations=文昌會文話&page=1&page_size=50 |
