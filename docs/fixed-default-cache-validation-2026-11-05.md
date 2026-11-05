# 固定默认缓存验证记录（2026-11-05）

本次只修改本地代码；未连接生产服务器、未复制数据库、未修改数据库持久配置、未部署。

## 已实现

六份固定默认结果使用原 Redis 服务、固定键覆盖、无 TTL，跨 worker 共享。版本由各槽位查询修订号及 DB/WAL 文件代次决定；checkpoint 可能保守失效。

WEB 主应用启动主动安排一次有限预热，不等待 HTTP 请求，不等待预热完成才就绪；同一主机只有一份、六项串行，有效结果跳过。新预热与既有 vocabulary 后台计算共用一个名额，在线请求不取得这个后台锁。缓存未命中时前台独立正常查库，允许前后台重复计算，不新增等待或 503。

六个固定回源路径使用当前文件的新只读连接，防止旧池连接在数据库替换后把旧结果标成新版本。动态查询保留原连接方式。

后台单项 SQL 30 秒、整轮 120 秒，使用 SQLite progress handler 中断实际 SQL；停止后先等实际线程退出，再关闭资源。失败不缓存异常，不新增自动重试或定时轮询。Redis 故障结束本轮，前台照常回源。

每槽 payload 上限 1 MiB、固定六槽。yubao 自动预热额外限制 20,000 个候选和约 1 MiB 数据，逐行读取；SQL CASE 阻止单个超大字段进入 Python。超限放弃预热，不截断正常用户请求。这个边界不是整个 Python/SQLite 进程 RSS 的硬上限。

专用 Redis 客户端最多 2 条连接/worker，连接和读写 socket 超时各 200 ms，自动重试 0 次，沿用原服务连接参数；不改其他客户端及服务器配置。200 ms 不是整个 HTTP 请求的总时限。

管理员两种普通清理入口保留版本命名空间，其他键最多每批删除 100 个，不累积全库键列表。compare 的统计、地点结果缓存及 feature_stats 结果缓存已取消，charlist 共用策略不变。旧 TTL 键自然过期，无线上删除操作。

SQL 泛化 total/count TTL 缓存取消，只保留两个首页默认 count。动态 yubao、N-gram、overview 不新增缓存。前端只为 yubao 两个本地键补已有 dbVersion 后缀；数据发布仍须同步更新前端版本，后端不向浏览器主动推送失效。

## 本地实际数据库测量

使用原本地 query_user.db（2.1 MiB）、dialects_user.db（2.6 GiB）、yubao.db（565 MiB）、villages.db（789 MiB），逐项串行 5 次，所有数据连接使用 mode=ro。操作系统文件缓存未清理，不能称为严格冷盘测试。

**Redis 使用进程内替身**。命中耗时不含真实 Redis 网络、HTTP、权限依赖或前端渲染；没有启动 Redis，不报告实际 MEMORY USAGE。小 count 直接查询仅约 0.3 ms，真实 Redis 往返可能抵消其耗时收益。

| 固定结果 | 无缓存中位数 ms | 命中中位数 ms（无网络） | 每次数据 loader SQL 数 | 响应字节 |
| --- | ---: | ---: | --- | ---: |
| sql:query_stored_count | 0.310 | 0.030 | 1 → 0 | 14 |
| sql:dialects_count | 10.498 | 0.029 | 1 → 0 | 17 |
| yubao:vocabulary_all | 1.512 | 0.058 | 1 → 0 | 9,447 |
| yubao:grammar_all | 0.302 | 0.031 | 1 → 0 | 3,536 |
| villages:gd:ngrams | 16.195 | 0.030 | 3 → 0 | 431 |
| villages:gd:tables | 229.406 | 0.218 | 264 → 0 | 48,007 |

六个 Redis envelope 合计 **62,848 字节（约 61.4 KiB）**，不含 Redis allocator、键和连接开销。所有结果均低于 1 MiB。

在上述查询已使文件缓存变热后，真实启动预热逻辑填满 **6 槽**，耗时 **255.6 ms**。整个独立测量进程峰值 RSS 为 **84.61 MiB**，包含模块导入、查询和响应等，不是预热增量，也不是完整 worker 的内存；不能外推生产收益。

SQL 路由首次白名单校验仍可能查询 schema，上表 SQL 数只统计数据 loader。yubao 无筛选全集用列表长度作精确 total，回源从列表加 COUNT 两条 SQL 减为一条。villages 整库表信息在此库每次包含 264 条 SELECT/PRAGMA（包括 dbstat 聚合），命中不再执行这些数据查询；N-gram 汇总从三条变为零条。

复现：使用现有虚拟环境执行 scripts/benchmark_fixed_default_cache.py，必须显式传 --query、--dialects、--yubao、--village 四个本地数据库绝对路径及 --output；--runs 限制 1–5，默认 5。脚本强制非 WEB 模式，无生产 Redis 地址、并行压测或数据库复制。

## 测试、复核与限制

新增覆盖固定键与修订、WAL/文件替换、空结果、损坏缓存、Redis 故障、超限旁路、精确参数与权限、前后台不等待、跨进程互斥、SQL 超时、只读限制、停机中断、yubao 读取边界、后台资源共享、普通清理保护，以及无 fcntl 平台的查库兜底。WEB lifespan 另测就绪前不等待预热和其他启动任务失败时清理已安排预热。

只读代码复核发现的两项问题——旧池连接的版本错配、预热读取阶段无界——均先加入失败回归再修复；第二轮复核未发现其他重要问题。

前端指定测试 **6 passed**；受改文件 lint **0 errors**，保留原文件已有 322 项模板缩进/换行等 warning，不做无关格式重写。前端提交 f2adfb9d。后端聚焦验证 **55 passed, 19 skipped**，19 项依赖真实 Redis 服务；所有本次新增测试均执行通过。命令（现有虚拟环境，_RUN_TYPE=MINE）：

~~~sh
python -m pytest tests/test_fixed_default_cache.py tests/test_fixed_cache_warmup.py tests/test_fixed_cache_routes.py tests/test_fixed_cache_clear_policy.py tests/test_yubao_thread_offload.py tests/test_sql_routes_thread_offload.py tests/test_sql_admin_permissions.py tests/test_vocabulary_execution_resources.py tests/test_vocabulary_warmup_scheduling.py tests/test_vocabulary_online_during_warmup.py tests/test_toponyms_resources.py -q --disable-warnings
~~~

实际本地六个预热结果与完整前台 loader 返回值逐项比较一致。真实 Redis 集成测试因没有相应本地服务而跳过，不能视作真实网络验证。

在尚未包含本次实现的原 dev 目录运行既有 villages/schema 与 phonology 两个测试文件，同样 **3 failed, 10 passed**：两项 villages 测试仍期待旧列名“自然村_规范名”，当前配置为“自然村_去前缀”；一项 matrix 测试建表缺现有代码需要的“音節”列。这些基线问题不在本次修改范围。

两个相同 compare 请求的验证结果：两组 charlist 合计只计算两次，统计函数执行四次，地点解析两次；feature_stats 两次请求执行两次统计。取消结果缓存会提高重复请求的计算成本，未测合适的实际参数，不宣称这些端点耗时不增加。

正常用户请求仍可与一个后台查询重叠，整个服务器总内存没有因此得到硬上限。尚未验证生产 2 核 2 GB 的混合流量、真实 Redis 内存和端到端延迟，不能据此声称 OOM 消失。Redis 重启/淘汰仍可能丢缓存；运行期间数据库版本变化由后续请求发现。数据库替换仍须遵守 SQLite 文件/WAL 的安全发布要求。
