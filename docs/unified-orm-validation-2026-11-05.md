# ORM 统一管理与只读连接实测（2026-11-05）

本次只修改、测试本地代码，没有访问、部署或改变生产服务器。

## 为什么前端有一处变化

此前前端提交 f2adfb9d 给 yubao 已有 localStorage 列表缓存的键加入既有 dbVersion，避免后端更新后浏览器继续无限期使用旧列表。界面和请求参数不变。前端持久缓存会绕过后端，因此后端版本缓存单独更新不能解决这件事。本次 ORM 重构无需再改前端。

## 统一范围

集中入口为 app/common/sqlite_orm.py：不可变策略、engine 创建、connect PRAGMA、Session 工厂、无 SQL 的 pool_status()、统一 dispose。四个模块保留 engine/SessionLocal/get_db 等旧导出，vocabulary 保留自定义数据库路径的测试工厂；Base、建表、迁移、权限和事务仍在原模块。延迟 COUNT 的独立 Session 复用原有 bind，不新增池、不复用请求 Session。没有把 ORM 和 raw sqlite3 混为一个池。

| profile | busy timeout | 外键 | SQLite cache_size | 每 worker 每库文件池 |
| --- | --- | --- | --- | --- |
| auth | 5000 ms | ON | SQLite 原默认 | 5，溢出 10，池等待 30s |
| supplements | 5000 ms | ON | SQLite 原默认 | 同上 |
| logs | 5000 ms | 保留原默认 | -64000（62.5 MiB 目标） | 同上 |
| vocabulary | 10000 ms | ON | SQLite 原默认 | 同上 |

池仍惰性建连接，非预分配 15 条；内存数据库保留 SQLAlchemy 原生池类型。WAL/失败回退 DELETE、synchronous=NORMAL、pre_ping 保持。SQL 初始化失败关闭 cursor 并传播异常，不新增重试。各库仍有独立事务。

资源边界：没有新增运行时并发任务、线程池、进程或常驻服务。池上限沿用现状，每库每 worker 最多 15 条，不代表整机上限。cache_size 是每连接页缓存目标，不是预分配或整个 worker RSS 硬上限，尤其 logs 原 62.5 MiB 配置仍值得后续单独压测调小。本轮不声称 ORM 重构直接减少内存或提高吞吐。弱引用注册表不强制保留临时 engine，没有请求结果常驻缓存或失败重试循环。停机在请求和后台任务排空后，用现有 asyncio.to_thread 机制释放 ORM 空闲连接；即便 Redis 或 ORM 清理异常，仍执行 raw 池关闭。dispose 不强制关闭已借出的连接。

## 只读连接：速度与内存取舍

六个固定默认缓存未命中/预热加载使用短生命周期只读连接，并非新建专用常驻池。主要用于避免数据库文件替换后复用旧 inode。只读标志不保证提速或省内存。

脚本 scripts/benchmark_sqlite_connection_lifecycle.py 对同一批本地真实文件、相同六个 loader，顺序运行三个策略，各 3 个独立子进程，每项查询 5 次。不使用 Redis 结果缓存。四个文件约为 query 2.1 MiB、dialects 2.6 GiB、yubao 565 MiB、villages 789 MiB。数据只读打开，不复制、不改变持久配置。所有策略均只读，变量是连接生命周期和连接页缓存预算。常驻策略各保留 4 条连接，并非完整模拟旧 FIFO 通用池的多连接/并发。

下表为三次进程内中位数的中位数；RSS 增量相对于相同模块导入后的基线，单位 MiB，查询单位 ms。

| 策略 | 空闲 RSS 增量 | query count | dialect count | yubao 词汇 | yubao 语法 | ngram | table 信息 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 常驻，16000 KiB/连接 | 47.09 | 0.039 | 12.181 | 0.679 | 0.044 | 13.708 | 248.475 |
| 短连接，2000 KiB/连接 | 4.33 | 0.333 | 11.985 | 1.525 | 0.332 | 17.239 | 229.149 |
| 常驻，2000 KiB/连接 | 9.39 | 0.041 | 11.087 | 1.245 | 0.042 | 13.824 | 235.429 |

这支持减少连接页缓存预算/连接保留时间能降低本轮测量中的空闲保留内存；简单重复查询复用连接更快。大查询没有可信的一致提速结论。不能把差值归因于只读标志，也不能外推为生产单 worker 必省约 43 MiB。操作系统页缓存、原生分配器保留和本机条件均影响结果；没有测生产并发吞吐。

原始测量在本地忽略目录 outputs/sqlite-connection-lifecycle.json。

## 验证

- 新测试先因集中模块未实现而失败，再实现；最终 16 项 manager 测试覆盖四个 profile、惰性连接、PRAGMA、显式提交、异常回滚、内存库、弱引用、池状态、dispose、WAL 回退、初始化异常、4 路并发归还、停机异常兜底。
- 聚焦运行 ORM、auth usage、user suggestions、admin trends、vocabulary deferred/routes/resource/cache lifecycle、fixed cache 测试：190 passed / 20 skipped（需要真实 Redis，本次不启动额外服务）。
- vocabulary routes/service 扩展运行：103 passed / 6 failed。改动前原 checkout（35cfb68）重跑同两文件，同样 103 passed / 同 6 failed：search API rate_limit、DOCX whitespace parsing、两项排序、map point location_label、location label 分隔符。没有将既有业务差异混入本次重构。
- 全局检索 app 运行时代码，create_engine/sessionmaker 实际调用已集中在 sqlite_orm；实验脚本、测试独立 engine 保持独立。
- git diff --check 无错误。
