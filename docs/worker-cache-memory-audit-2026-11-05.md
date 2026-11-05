# Worker 缓存与连接内存审计（2026-11-05）

## 本次修复

vocabulary.script_variants 原先另建 `OpenCC('s2t.json')`，现在引用 `app.common.s2t.opencc_s2t`。保留现有 OpenCC 配置、T2S 转换器、函数签名与 LRU 缓存。不新增任务、线程、进程或服务器配置。跨 worker 仍各有自己的转换器；本次消除的是同一 worker 内的重复实例。

原生绑定 Python 包装器的 convert 只做输入编码后调用底层转换；应用没有修改共享转换器配置。新增测试覆盖对象复用、5组简繁/混合/空白输入，以及4线程1000轮公共/vocabulary交叉调用。此测试是本地有界验证，不在生产增加并发。实验不是对所有版本底层库线程安全的形式证明，升级绑定时应继续执行回归。

### 验证

- 新测试修复前：复用断言失败、其余6项通过；修复后7项通过。
- 现有 query_resources、compact_groups、service 加新测试：80 passed / 5 failed。
- 在独立测试进程将 `_S2T` 恢复为旧的独立实例：原有测试73 passed / 相同5项failed。失败涉及旧导入解析、查询预期、地点标签等，不是此次实例复用引入。没有改动这些失败。
- 本地macOS/Python3.12/OpenCC，先加载公共转换器，再执行修改前/后的 script_variants 源码，各3个独立进程；总RSS中位数34.719 → 27.031 MiB，减少约7.688 MiB/进程。不是生产实测节省，也不表示热替换后分配器立即归还内存。
- 原始记录位于忽略目录 `outputs/worker-memory-20261105/shared-s2t-*`；本次未部署。

## 哪些跨 worker 共享

| 层 | 是否跨worker共享 | 资源位置 |
|---|---|---|
| Redis同实例/DB/键 | 是 | Redis进程；worker仍有连接、收发、JSON编解码临时对象 |
| 方言预热、_variant_cache、Python dict | 否 | 各worker Python堆 |
| script_variants lru_cache | 否 | 各worker Python堆；8192/4096是条数上限，不是字节上限 |
| GIS geometry LRU | 否 | 各worker Python/原生几何对象；默认2048项 |
| ComputeCache及feature_cache | 否 | 各worker堆；前者100项/1小时并deepcopy，后者未设容量 |
| toponyms ResultCache | 否 | 各worker序列化bytes；payload上限4MiB、256项、单项128KiB、TTL30秒 |
| schema/PRAGMA等元数据缓存 | 否 | 各worker小型字典；先核实数量，不优先迁移到Redis |
| SQLite私有页缓存 | 否 | 各worker内的各条SQLite连接；同一DB走ORM/raw也不共享 |
| SQLAlchemy Session identity map | 否 | 单Session对象集合；不是跨请求查询结果缓存 |
| Linux文件页缓存 | 通常可复用同一文件的页 | 内核；不同于SQLite页缓存 |

不能把上述缓存全部搬到Redis：本地静态索引/原生几何/转换字典不适合频繁JSON化；Redis命中也要付出序列化、网络、解码与临时对象成本。

## 生产Redis只读快照

2026-11-05下午，连接既有应用使用的172.28.199.1:6379/0。使用INFO、CONFIG GET、最多4轮SCAN和最多256键的MEMORY USAGE(SAMPLES 1)/STRLEN，不读取业务值，不创建键，不清缓存、不改配置。

- used_memory约1.51MiB、RSS约2.23MiB；used_memory_dataset约0.53MiB。
- 进程历史分配峰值47.82MiB，不是worker峰值，也不是当前占用。
- 31键；8个vocabulary默认结果合计字符串payload340579B（约333KiB），MEMORY USAGE约374KiB；另有少量元数据；本次未发现vocabulary ondemand结果键。
- `maxmemory=0`，当前未设Redis内存上限；`noeviction`并不等于现状有内存硬上限。
- 当前vocabulary参数未通过环境覆盖，按源码默认max_keys=128、max_bytes=128KiB。max_bytes是每个按需值的最大UTF-8 payload，并非命名空间总大小；按需结果当前集合的payload预算为16MiB/DB namespace，各worker共同使用，不乘worker数。
- 16MiB不包含默认永久结果、旧版本待清理键、元数据、锁、其他模块键、连接缓冲及分配器开销。8个默认结果绕过按需单值/条数限制。其他Redis模块多有TTL但不统一限制总字节。

建议先在各业务命名空间做单值及总量准入；已有缓存不因本次OpenCC复用而增加。不要直接更改全局淘汰策略：同Redis还有认证、权限和限流相关键，应先分析丢键语义。过大可选结果不缓存；失败沿用有限超时和既有回源/忙响应路径，避免新建无限重试后台任务。

## SQLite/ORM不是一套配置

生产SQLite3.46.1、SQLAlchemy2.0.55。只构造同参数的只读engine并查询PRAGMA，未导入带建表/迁移副作用的应用数据库模块；池参数是该版本默认值，不是读取现有worker实际连接数。

| 路径 | 页缓存设置 | 连接生命周期 |
|---|---|---|
| app/sql/db_pool.py | -16000，约15.625MiB目标/连接；temp_store=MEMORY | 各worker自建池；启动预建23条，其他路径可懒建池；每池允许短时2倍连接 |
| auth ORM | 未显式设置；生产新只读连接读到-2000，约1.953MiB目标 | QueuePool默认保留容量5，另允许10条溢出；按需创建，非启动就创建15条 |
| supplements ORM | 同上 | 同上 |
| vocabulary ORM | 同上 | 同上；其raw SQL若经session.connection执行，仍使用ORM连接 |
| logs ORM | connect hook明确覆盖-64000，约62.5MiB目标 | 同上；是最值得单独调小的ORM缓存预算 |
| GIS _ReadOnlyPool | 未显式设置页缓存，另有geometry LRU | 初始化3条，上限6条 |
| toponyms resources/streaming | -4096，4MiB目标；temp_store=FILE | 专用只读连接，随上下文/流结束关闭 |
| sql_routes/sql_tree/vocabulary_sql等直接sqlite3.connect | 未统一覆盖页缓存 | 多为操作后关闭，应逐路径核实finally关闭；不是通用池配置 |

PRAGMA cache_size是连接级建议目标；ORM不会绕过SQLite缓存，也不自动缓存所有查询结果。ORM Session.close释放事务和对象持有并归还池连接，通常不是关闭物理连接。相同数据库可同时走ORM和raw池，因此会有两套连接缓存。

## 具体优化顺序与性能代价

1. 复用OpenCC：本次已完成。保留字典和热转换路径，本地实测约7.7MiB/worker，转换结果测试通过，不以降低命中率换内存。
2. 方言预热对象复用：本地原型Python存活9.83→2.37MiB，关闭追踪后的RSS增量13.14→5.02MiB。保留记录与顺序、摘要一致，尚未集成；完整接口回归后再落地，不直接删除预热。
3. logs ORM按连接降低缓存预算：此前本地相同日志读负载-64000→-4000，SQLite分配32.69→4.83MiB，差27.86MiB/受测热连接。实际线上是否能省这些，取决于连接读负载；只写少量日志未必有这么多缓存。先保持池数量，单独测管理统计查询的P95、I/O与锁等待。
4. 通用池按库降低目标至候选4MiB左右：此前本地受测热连接dialects约省8.8MiB，characters约12.0MiB，yubao/villages各14.2MiB；小query库为0。不要把这些乘全部池数量当作生产已分配。冷缓存/不重复扫描影响可能较小，热点工作集大于新预算的重复查询可能变慢。
5. auth/supplements/vocabulary ORM：目前约2MiB目标，优先保留，不向上统一为通用池的15.6MiB。测checked-out高水位、等待与嵌套借用后再决定pool_size/max_overflow；过小会增加排队，过大会放大请求和缓存峰值。ORM大查询优先SQL投影/聚合/分页，避免全量实体.all；并确保Session finally关闭。
6. GIS/Compute本地缓存：按字节预算+条目上限+大项拒绝准入，保持本地热点。feature_cache补容量和淘汰；ComputeCache的deepcopy需结合调用者是否修改返回值评估，不能直接删掉。命中率下降会增加CPU/数据库工作，需配合现有任务并发上限；不启动新后台常驻任务补算，不无限重试。
7. Redis：当前约1.5MiB，不应优先清理或缩小。保持已共享的词表结果/精确total；给尚无总量边界的业务缓存补准入和失效策略。Redis失败回源时必须维持有界查询并发，避免所有worker同时重算。
8. toponyms：已有小SQLite缓存、只读短生命周期和磁盘临时表，结果缓存也已限制为每worker4MiB payload/256项/单项128KiB/TTL30秒。三worker的payload预算合计12MiB，不是实际占用或含Python元数据的RSS上限。暂不继续挤压；先测再改。

不要同时缩池、降页缓存、删预热，否则性能回退难以归因。先取同数据/同参数/同并发的基线，再一次改一类，对比新worker稳定期PSS、接口P50/P95、连接等待、CPU/磁盘读取及错误率。尚未测得的内存收益不作数值承诺。
