# `/api/notes` 查询性能：只读分析与改动计划

日期：2026-10-08。约束已补充：部署端为 **2 核、2 GiB RAM**，**即使默认 `q` 为空、没有任何筛选，单次 `/api/notes` 也超过 10 秒**；Redis 已由用户排除，不能改服务器配置，只考虑后端与数据库。分析范围：当前代码、本机 `data/dialects_user.db` 与 `data/query_user.db`；分析实验未连接部署服务器，也未修改持久数据库。下文“实测”只代表这台机器上的 SQLite 3.53.2，服务器收益均为待验证的预测。文末记录后续获准实施的改动。

## 结论

1. **当前最小方案是“全表行数减无效行数”，无需新增总数元数据表。** 空 `q`、无地点/分区时不走 FTS、IPA 或 `UNION`；慢处是每次对约 177 万行执行有效注释表达式来算精确 `total`。只给无效行建部分索引，本机只有 6 行、索引约 4 KiB；`COUNT(*) FROM notes` 减去该索引上的无效行计数，与原结果完全相同，并随数据自动更新。临时副本中原计数约 117 ms，改写约 0.38 ms。服务器 10 秒是否全部发生在 count，仍需分段确认。
2. **上一版把数项可选优化列得过早。** 逐字符 IPA FTS、临时表主键与强制 JOIN 顺序、范围下推、连接池调整都不影响已确认的空 `q`、无范围路径；它们应等这一路径改完、再用非空或有范围请求的服务器耗时决定是否做。`notes(音節)` 普通索引也不能改善空词请求。
3. **非空词的潜在瓶颈已有证据，但不宜一次全部实施。** 现有 FTS5 只覆盖注释，默认双字段还扫描 IPA；本地实验说明范围下推和稀疏词 IPA FTS 有潜力，高频 `ts` 在完整路径中却可能不赢。先修明确的空词瓶颈，再按真实查询分布选择一个后续改动。

## 证据与请求路径

代码位置：`app/routes/notes.py`、`app/service/notes.py`、`app/service/geo/getloc_by_name_region.py`、`app/sql/db_pool.py`、`app/sql/index_manager.py`、`app/lifecycle/startup.py`、`app/common/config.py`。

```text
HTTP → 鉴权/限流 → run_in_threadpool(query_notes)
     → 若有 locations/regions，在 query_user.db 展开为简称
     → dialects_user.db：
       非空 q：FTS MATCH [UNION] 全库 IPA LIKE
             → 候选 rowid 回表验证注释/地点
             → CREATE TEMP TABLE matched_rowids
             → COUNT(*) + JOIN/ORDER BY/LIMIT/OFFSET 取页
       空 q：逐行验证注释 → COUNT(*)
             → 再执行一遍匹配条件、JOIN、排序、取页
```

本机数据库与 9 月 29 日设计文档中的旧快照不同：现有 `notes` 为 **1,768,771** 行、3,012 个简称；按 API 的有效注释条件为 **1,768,765** 行，仅 6 行无效。`notes` 表约 92.3 MiB，`idx_notes_abbr` 约 32.6 MiB，`notes_fts_data` 约 18.8 MiB；整个 `dialects_user.db` 约 2.6 GiB，主要大小不能归因于 notes 表。`query_user.db` 约 2.1 MiB。数据量、索引是否存在都必须在服务器重新核对。

关键查询计划（本机 `EXPLAIN QUERY PLAN`）：

| 路径 | 计划要点 | 含义 |
| --- | --- | --- |
| 注释 `MATCH` | `SCAN notes_fts VIRTUAL TABLE INDEX ...:M1` | 真正使用 FTS 倒排索引 |
| IPA `COALESCE(音節,'') LIKE '%…%'` | `SCAN notes` | 当前库扫描主表；前导 `%` 不能用 B-tree 定位 |
| 双字段 | `MERGE (UNION)`，一支 FTS，一支 `SCAN notes`，随后 `SEARCH notes USING INTEGER PRIMARY KEY` | FTS 变快也要等待另一支和回表 |
| 空 `q` 总数 | `SCAN notes` | 对全部行执行 `TRIM(COALESCE(...))` |
| 有范围的空 `q` 总数 | `SEARCH notes USING INDEX idx_notes_abbr` | 能按简称缩小范围，但仍回表检查注释 |
| 有范围的空 `q` 取页 | `SEARCH ... idx_notes_abbr`、再次 `SEARCH notes ... rowid`、`USE TEMP B-TREE FOR ORDER BY` | 当前双层 JOIN 带来重复回表和排序 |

`notes_fts` 是 `content=''` 的 FTS5 表；`SELECT count(*) FROM notes_fts` 报“不支持扫描”属于这种表的预期行为，不能据此判断 FTS 失效。以 `MATCH '"文 白"'` 查询有 42 个候选，约 1 ms。FTS 的字符分词/短语语义与原文 `LIKE '%文白%'` 不完全相同，不应拿两个计数直接判断索引是否完整。

## 复现的查询场景

测量方法：使用 `mode=ro` 打开主数据库，临时表只建在 SQLite TEMP 空间；模拟 `query_notes` 的 SQL，页大小 50，`PRAGMA temp_store=MEMORY`、`cache_size=-16000`。首轮时间含冷一些的文件页；后续对照使用同一连接多次运行取中位数。未计 HTTP、序列化和网络。时间会随文件缓存变化。

| 模拟请求 | 本机结果 | 首轮分段耗时 | 主要原因 |
| --- | ---: | ---: | --- |
| `GET /api/notes` | 总数 1,768,765 | 总数 679 ms；取页 0.6 ms | 空词全库逐行验证注释；暖缓存总数中位数仍约 134 ms |
| `?q=文白&search_fields=detail` | 42 条 | 建命中表 2.4 ms；取页 0.3 ms | FTS 有效，且候选少 |
| `?q=文白`（默认双字段） | 42 条 | 建命中表 344 ms；取页 0.2 ms | IPA 分支虽命中 0 行，仍扫全库 |
| `?q=上`（默认双字段） | 22,691 条 | 建命中表 396 ms；取页 31 ms | IPA 全扫 + 大命中集排序 |
| `?q=ts&search_fields=pronunciation` | 183,168 条 | 建命中表 479 ms；取页 104 ms | IPA 子串扫描 + 大命中集临时表和排序 |
| `?regions=閩-閩南` | 96,316 条；范围展开为 106 个简称 | 总数 43.5 ms；取页 113 ms | 注释验证和双层 JOIN/排序；暖缓存当前取页中位数 23.4 ms |
| `?q=文白&regions=閩-閩南` | 1 条 | 建命中表 433 ms | 小范围仍先走全库 IPA 分支 |
| `?q=文白&page=100` | 0 条 | 建命中表 368 ms | 即使页不存在，仍先构造全量结果和精确总数 |

范围语义由 `query_user.db` 的 `dialects` 展开。`閩-閩南` 是仓库里的真实分区；请求中必须 URL 编码。显式单地点可用 `locations=1883廈門`，该简称在 notes 中约 738 行。以上是猜测的代表性用法，不是服务器访问日志中的真实请求分布。

### 已确认最慢用法：空 `q`、无范围

用户补充：服务器在 `GET /api/notes`（默认空 `q`）仍超过 10 秒。这个分支的本机复测：`EXPLAIN QUERY PLAN` 对总数显示 `SCAN notes`；5 次中位数约 **285 ms**（前一次暖缓存实验约 134 ms，首次约 679 ms）。现有第一页取完整 5 列中位数约 **0.07 ms**，直接从 notes 取页约 **0.05 ms**。在 TEMP 中把计算过的精确总数保存为一行后，读取该行约 **0.002 ms**。因此这条请求要优先消掉的是**每次重新全表计算精确总数**，第一页 JOIN 只是次要清理。

复核后的更小方案是为**无效**注释建部分索引，而非保存一个可能过期的总数：

```sql
CREATE INDEX idx_notes_invalid_detail ON notes(註釋)
WHERE TRIM(COALESCE(註釋, '')) IN ('', '_', '-');

SELECT
  (SELECT COUNT(*) FROM notes)
  - (SELECT COUNT(*) FROM notes
     WHERE TRIM(COALESCE(註釋, '')) IN ('', '_', '-')) AS total;
```

因为 `COALESCE` 后结果非 NULL，`IN ('','_','-')` 恰是 API `NOT IN` 有效条件的补集。临时副本的 `EXPLAIN` 对无效计数显示 `USING COVERING INDEX idx_n_invalid`，值为 6；该索引仅增加一个 4 KiB 页。5 次中位数：原有效计数约 116.7 ms，改写总计约 0.38 ms（临时表在内存）；真实本机 `COUNT(*) FROM notes` 约 6.3 ms。服务器仍须复测，且建索引本身需要一次全表读取。这个索引会随着 `notes` 写入自动维护，不需元数据版本、重建触发器或每 worker 的缓存失效逻辑。若服务器连裸 `COUNT(*)` 都很慢，再考虑离线精确总数元数据；目前不应先增加它。

### 只读等价 SQL 对照

| 对照（3 次中位数） | 当前查询 | 临时改写 | 结果是否相同 |
| --- | ---: | ---: | --- |
| `q=文白`，106 地点：命中集构建 | 111.1 ms | IPA 分支先筛地点：14.4 ms | 都 1 条 |
| `q=ts`，106 地点：命中集构建 | 123.2 ms | IPA 分支先筛地点：20.3 ms | 都 13,696 条 |
| `q=ts`，单地点：命中集构建 | 106.0 ms | IPA 分支先筛地点：0.9 ms | 都 120 条 |
| `q=ts`，全库：建表/取页 | 132.0 / 31.4 ms | `rowid INTEGER PRIMARY KEY` 临时表：139.9 / 0.1 ms | 都 185,725 条；此高频样本不能证明稀疏结果也快，见下方计划器陷阱 |
| 空词，106 地点：取 50 条完整列 | 23.4 ms | 直接从 notes 过滤、排序、取页：0.1 ms | 都 50 条 |
| 空词，全库总数 | 133.9 ms | `COUNT(*) FROM notes`：6.3 ms | **不等价**：后者多算 6 行，不能直接上线 |
| 空词，全库总数（新对照） | 临时副本原有效计数 116.7 ms | 裸总数减无效部分索引计数 0.38 ms | **等价**：都为 1,768,765；真实库收益待部署验证 |

另外，临时复制音节列并建立覆盖索引后，`ts` 的 IPA 扫描中位数从主表约 107.5 ms 到临时索引约 64.1 ms；两者存储位置不同，只能说明“缩小扫描字节”有价值，不能作为精确收益预测。曾测试“有效注释”部分索引，计数约 15.8 ms，但它收录几乎全部 177 万行；相比只收录 6 行的**无效注释**部分索引，已无必要。上述实验均未向主数据库写索引。

### 候选方案：2 GiB 约束下的 IPA FTS5 临时索引实验

再次用 `mode=ro` 打开主库，只在 TEMP 中建立一个 `content=''` FTS5 表：每个 IPA 原始字符分隔为单字符 token，`rowid` 与 `notes.rowid` 相同。索引约 **25,075,712 字节（23.9 MiB）**，本机一次性构建约 1.47 秒。**该索引暂不列入首轮；若后续采用**，须在离线构建数据库时生成，不能在 2 GiB 服务的每个 worker 启动时重建。查询的 FTS 短语只负责找候选，最终仍对原 `notes.音節` 执行现有字面 `LIKE`，因此假阳性会被过滤。任意无法安全生成 token 的输入必须走原扫描路径，不能漏结果。

| IPA 查询 | 全表 `LIKE` 中位数 | 临时 IPA FTS 候选 + 原值 `LIKE` 校验中位数 | 精确结果数 | 判断 |
| --- | ---: | ---: | ---: | --- |
| `文白` | 82.6 ms | 接近 0 ms | 0 | 默认中文注释搜索不再被无命中 IPA 全扫拖慢 |
| `上` | 86.2 ms | 接近 0 ms | 0 | 单汉字同理；库中仍有 5 行 IPA 包含汉字，不能直接省略 IPA 分支 |
| `lo3` | 77.9 ms | 4.4 ms | 439 | 稀疏 IPA 子串显著收益 |
| `ts` | 112.7 ms | 72.2 ms | 183,168 | 高频短词仍需访问大量候选，收益有限 |
| `ã` | 87.4 ms | 72.4 ms | 35,541 | 组合附加符被 FTS 分词忽略，候选达 444,832，接近扫描成本 |

这是**单分支**测量。完整默认双字段还需 `UNION`、有效性回表与临时表；本机 `文白` 的命中集构建从约 93 ms 到 0.4–0.6 ms，`上` 从约 109 ms 到 17–38 ms，`lo3` 从约 86 ms 到 5–8 ms。`ts` 在不同重复实验中，新路径建表约 133–288 ms、原路径约 132–145 ms，说明**高频词不能一律走 IPA FTS**。若后续采用，须根据实际查询词频与服务器基准选路；不能现在预设固定阈值。

新表必须按数据构建版本与 `notes` 同步，重建/更新时验证索引覆盖。普通 `FTS5 trigram` 对 1–2 字符查询帮不上忙；原始 IPA 直接放进 `unicode61` FTS 也无法实现任意子串匹配，关键是逐字符 token 化。查询构造要测试 IPA 字母、数字、声调、组合附加符、标点、空白和 `%`/`_` 字面匹配，确保 FTS 只减少候选、不改变结果。

分页还有一个容易误判的计划器陷阱：仅把临时表改为 `rowid INTEGER PRIMARY KEY`，SQLite 对稀疏 42 条结果可能采用 `SCAN notes` → `SEARCH matched`，本机取页约 47 ms；改为 `FROM matched CROSS JOIN notes ON notes.rowid=matched.rowid ORDER BY matched.rowid` 后，计划变为 `SCAN matched` → `SEARCH notes USING INTEGER PRIMARY KEY`，约 0.02 ms。主键与驱动顺序必须一起实施并用 `EXPLAIN` 验证。

## 为什么 2 核 2 GiB 服务器会比本机慢得多

下面按证据强度排序，**不是已确认的服务器根因**：

1. **扫描与缺页放大（高可能）。** 默认空词请求扫描注释来算总数；只有非空双字段请求才扫描 IPA。服务器只有 2 GiB，运行整个应用、3 个 worker、多数据库连接池与操作系统后，留给数据库页缓存的空间更少。若读入的页频繁被挤出或发生 swap，本机百毫秒的扫描可能变成数秒；并发请求会相互放大。
2. **当前索引未随代码部署（可直接核验）。** 本机没有 `idx_notes_ipa`。`app/sql/index_manager.py` 有建索引代码，但 `AUTO_INDEX` 默认关闭，Dockerfile 也未开启。因此服务端可能仍扫主表。即使补上该覆盖索引，`LIKE '%…%'` 仍是 O(N)，只能减轻而非根治全库无范围搜索。不要为它开启全库 `AUTO_INDEX`，那还会处理其他大表。
3. **命中表与重复回表（确定存在）。** 非空词做全量候选、`UNION`、有效注释回表、临时表、再次回表和排序；高频短词与深页更重。空词还做精确总数全扫，有范围取页多一次同表 JOIN。2 核下这些计算比本机更容易与其他请求争 CPU。

按用户信息，**Redis 不作为此次方案的排查方向或优化目标**。服务器数据文件、索引和请求分段耗时仍须只读核对；这决定 10 秒中究竟多少来自上述查询本身。

## 建议的实施顺序与预计收益

收益是基于上面的本机对照，对**对应场景**的预测，不是服务器端承诺。2 核 2 GiB 上，磁盘缺页、并发与内存压力会改变各路径的相对成本；10 秒请求要通过 SQL 分段计时核实主耗时。

| 优先级 | 改动 | 位置 | 对应场景预期 | 风险与验证 |
| --- | --- | --- | --- | --- |
| P0 | **只建无效注释部分索引并改写无范围空词的 total**：裸行数减无效行数；页 SQL 暂不动 | 数据库迁移/构建流程、`app/service/notes.py` | 临时副本 116.7 ms → 0.38 ms；真实本机裸行数约 6.3 ms。若服务器 10 秒主要来自有效性全扫，预计会大幅缩短 | 一次索引构建会扫表；服务器验证 1,768,765 与现有结果相同、计划使用该索引 |
| P0 | 只记录空词的连接池等待、count、page 三段耗时，比较改前改后 | `app/service/notes.py`，或一次性诊断脚本 | 确认是否消掉服务器的 10 秒主耗时 | 不需要先引入通用监控系统 |
| 后续条件项 | 若**有范围的空词**仍慢，再去掉其取页的同表 JOIN | `app/service/notes.py` | 本机 106 地点取页 23.4 ms → 0.1 ms | 不影响无范围空词；保持排序与范围语义 |
| 后续条件项 | 若**带范围的非空词**仍慢，再把范围筛选推入 IPA 分支 | `app/service/notes.py` | 本机 106 地点命中集约 6–8 倍、单地点约百倍 | 大范围可能退化，先看实际请求与计划 |
| 后续条件项 | 若**无范围的非空词**仍慢，再比较普通 IPA 覆盖索引与逐字符 IPA FTS；只实施经服务器基准证明有益的一项 | 数据库构建流程、`app/service/notes.py` | 稀疏词 FTS 本机收益大，高频 `ts` 可能无收益 | FTS 约 24 MiB 且需语义/同步设计，不应纳入首轮 |
| 后续条件项 | 仅当大命中集**取页**显著慢，再一起实施临时表主键与从 matched 驱动的 JOIN | `app/service/notes.py` | 本机高频命中取页 31 ms → 约 0.1 ms | 单独加主键会让稀疏页退化，必须同时验证计划 |

**删去上一版的首轮过度改动：**不新增 `notes_search_meta` 表；不建收录约 177 万行的“有效注释”部分索引；不先建 IPA FTS、普通 IPA 索引或调整连接池；不为无范围空词改分页 JOIN（本机已约 0.07 ms）。这些方案保留为特定慢场景被服务器测量证实时的备选，而不是一次性改动包。若部署端裸 `COUNT(*)` 本身仍慢，才重新比较元数据表和其他办法。

## 可执行的验证计划

### 1. 服务器只读采样

首轮只测 `GET /api/notes`：改前改后各采样多次，记录连接池等待、原有效计数、裸 `COUNT(*)`、无效行计数、取页和完整服务耗时。若首轮解决 10 秒问题，再按用户实际慢的参数选取一个后续场景做对照；不预先对所有查询词开展整套压测。

只读核对示例（在实际数据目录执行）：

```sql
SELECT COUNT(*) FROM notes;
SELECT COUNT(*) FROM notes
 WHERE TRIM(COALESCE(註釋, '')) IN ('', '_', '-');
SELECT name, sql FROM sqlite_master
 WHERE type = 'index' AND tbl_name = 'notes';
EXPLAIN QUERY PLAN
 SELECT COUNT(*) FROM notes
 WHERE TRIM(COALESCE(註釋, '')) NOT IN ('', '_', '-');
```

若裸 `COUNT(*)` 或连接等待仍达到数秒，再记录服务 RSS、swap 与 I/O 等待并继续定位；此时才重新评估元数据总数或连接池。用户已排除 Redis，本轮不以它为优化对象。

### 2. 最小代码改动与回归

1. 在 `tests/test_notes_service.py` 只补空词无范围的精确总数测试：包含有效注释与 `NULL`、空白、`_`、`-`，并检查新增/删除无效行后计数仍准确；确认第一页项目与顺序不变。
2. 在离线数据库副本建立 `idx_notes_invalid_detail`，核对 `EXPLAIN QUERY PLAN` 与原计数结果；把同一索引纳入数据库发布/迁移流程。不要开启全库 `AUTO_INDEX`。
3. 仅改 `query_notes` 的空词无范围 `total` SQL，分别计时连接等待、count、page。跑 `tests/test_notes_service.py`、`tests/test_notes_real_database_contract.py`、`tests/test_notes_route.py`，并在服务器对照默认空词请求的 p50/p95。
4. 若 10 秒仍存在，按实际慢的分段重新定位；若空词达标，再看非空/带范围请求基线，逐项决定是否实施上表的条件项，不预先打包。

本报告的全部实验只读取主数据库；`CREATE TEMP TABLE`/TEMP 索引仅存在于实验进程内，退出后消失。

## 获准后的最小实施与部署步骤

已在 `app/service/notes.py` 将**空 `q` 且没有地点/分区**的精确总数改为全表行数减无效注释行数；其他查询和取页 SQL 保持原路径。`app/sql/index_manager.py` 提供只建立这枚部分索引的独立命令，并在已有 `AUTO_INDEX` 流程中登记该索引。没有开启 `AUTO_INDEX`，也没有建立 IPA 索引、IPA FTS 或总数元数据表。

部署新代码时，对 API 实际使用的 `dialects_user.db` 执行一次：

```bash
python -m app.sql.index_manager notes-invalid-detail data/dialects_user.db
```

该命令只执行 `CREATE INDEX IF NOT EXISTS idx_notes_invalid_detail ...`，可重复运行；若路径不存在会报错，避免误建空数据库。首次创建会读取 `notes` 表，应安排在部署切换前完成。**只更新代码而没有在服务端数据库建立此索引，无法得到预期加速。**不需要修改服务器配置或 Redis。

上线前后用同一数据库核对总数和计划：

```sql
SELECT COUNT(*) FROM notes
WHERE TRIM(COALESCE(註釋, '')) NOT IN ('', '_', '-');
SELECT (SELECT COUNT(*) FROM notes) -
       (SELECT COUNT(*) FROM notes
        WHERE TRIM(COALESCE(註釋, '')) IN ('', '_', '-'));
EXPLAIN QUERY PLAN SELECT COUNT(*) FROM notes
WHERE TRIM(COALESCE(註釋, '')) IN ('', '_', '-');
```

前两项必须相等；最后一项应出现 `USING COVERING INDEX idx_notes_invalid_detail`。随后对默认 `GET /api/notes` 连续采样并记录服务端耗时。若仍接近 10 秒，应分别计时连接池等待、count 和取页，再按实际慢段处理；当前本地测试不能替代服务器测量。此次没有修改本机的持久 `dialects_user.db`。

## 后续确认的注释规则与范围计数

用户进一步确认：`notes.註釋` 只保留含中文汉字或拉丁字母的记录；带变音符号的拉丁转写和纯英文保留，纯数字与纯符号排除。`dialects` 主表的读音行不因此删除。用新筛选函数只读扫描当前库的 1,768,771 条 `notes`，有 **35,607** 条不满足规则，重建后预计保留 **1,733,164** 条；其中被排除的大量是数字标记和符号。这个数量远大于旧 API 排除的 6 条 `_`、`-`。新规则必须由 `dialects-build` 生成新数据库及配套 `notes_fts`，不能仅在后端改 `total`。

完整重建后的数据库将 `PRAGMA user_version` 设为 `20261008`。后端仅在此版本上使用简化的空词路径：无范围时 `COUNT(*) FROM notes`，有范围时 `COUNT(*) FROM notes WHERE 簡稱 IN (...)`，取页也直接从 `notes` 查询。旧数据库保持前文的有效性过滤和精确计数。`append`/`update` 不会把旧数据库标记为新版本；它们在已完整重建的新库上仍按同一规则筛选。

本机只读对照：106 个地点的范围计数，旧有效性表达式约 9.35 ms，直接按简称计数约 1.31 ms，后者使用 `idx_notes_abbr` 覆盖索引。空词范围取页还可去掉重复的同表 JOIN。**非空词的 `total` 仍是匹配集行数，不能改成全库或地点行数；其 IPA 子串扫描不受本轮计数简化影响。**

部署次序：先用更新后的 `dialects-build` **完整重建** `dialects_user.db`（及相应 FTS），核对 `PRAGMA user_version` 为 `20261008`、注释规则和请求结果，再替换服务端数据库；后端代码可先部署，它在旧库上继续使用旧路径。新库已无需要计数排除的行，因此不依赖 `idx_notes_invalid_detail`；该索引继续服务于尚未替换的旧库。没有在本机持久数据库上执行重建或删除。
