# Toponyms / GIS 通用连接池实施计划

用户已授权直接改动，本地顺序执行，不访问生产。使用现有隔离 worktree。

目标：扩展通用 SQLiteConnectionPool 的只读策略，接入 toponyms / GIS；不复制数据库、不修改其 journal_mode、不改 API 合同、不新增执行线程或提高在线并发。旧通用池默认配置保持。

配置：toponyms readonly/cache=4096KiB/temp=FILE/busy=100ms/idle=1/总上限=3/等待=0；GIS readonly/cache=2000KiB/temp=FILE/busy=5s/idle=3/总上限=6/等待=5s。只读池惰性创建，归还超额即关闭。toponyms 仍有跨 worker heavy=2/light=1/tree=1子集准入，流式每批256行，无新增全量缓冲。总连接上限是每worker；页缓存不是RSS硬上限。无新重试任务，连接失败传播；读连接异常归还时丢弃，下个请求按需恢复。并发上限不因复用而增加。

选择共用实现和独立只读 profile；不直接复用旧默认的可写/WAL/16MiB/MEMORY配置，也不继续保留两套池实现。toponyms可能增加空闲保留内存，GIS主要改善生命周期，不预设性能获益。

- [x] 为只读策略、惰性创建、严格容量、回收清理、超时/流式取消、原子替换文件写失败测试并确认失败。
- [x] 扩展 app/sql/db_pool.py：不可变只读策略、profile键隔离、资源状态清理（progress/trace/authorizer/事务/游标由调用方关闭），失效连接丢弃，不带请求状态回池。只读连接记录文件身份，在借用时丢弃旧inode空闲连接；借出中的连接在归还时检查并丢弃，不中断进行中查询。
- [x] app/service/toponyms/resources.py 使用通用只读借用上下文，保留deadline映射；streaming.py 独占借用直到cursor关闭并清除取消回调。
- [x] app/geo_query/engine.py 移除_ReadOnlyPool，使用同一通用管理器，保留API；初始化失败不留下私有资源。全局关闭后允许引擎再次获取新池，不保留永久关闭的池引用。
- [x] 本地运行 tests/test_sql_db_pool.py、toponyms资源/route/auth、GIS实测库测试；旧代码先跑基线，记录数据依赖。
- [x] scripts/benchmark_geo_pools.py：对本地真实4.9GiB toponyms/181MiB GIS，只读比较改前/改后相同实际SQL或engine查询；独立进程顺序执行，记录连接数、空闲RSS、首次/重复耗时和CPU。不得将本机测试外推为生产保证。
- [x] 独立复核、git diff --check、提交并合入本地dev，保留用户未提交文件。报告收益与负收益、边界和未测部分。

实测决策：2MiB初测 points prefix 中位数约慢14%，故toponyms最终保留原4MiB；GIS维持SQLite原默认约2MiB。统一实现不等于所有库同一预算。

最终报告：docs/shared-geo-pools-validation-2026-11-05.md。独立复核发现并修复GIS文件替换后的缓存混代；最终268 passed / 20 Redis-dependent skipped。toponyms简单查询收益显著但绝对约0.4ms，重查询及GIS点查询无提速；内存收益较小，均按实测报告。
