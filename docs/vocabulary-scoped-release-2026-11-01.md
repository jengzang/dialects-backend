# Vocabulary 地点范围查询：正式实现与量化报告

日期：2026-11-01。基线 `b8d90fe`；全部修改、验证和测量在本地 dev 完成，没有创建分支，没有连接/改动服务器，没有部署。

## 1. 最终实现与提交

| 提交 | 改动 |
|---|---|
| `a1cdceb` | 共享有界范围规划；entries 仅首页、计数缓存 miss 时启用 |
| `5371580` | standard-words 用小范围地点索引读取后聚合 |
| `53c865a` | map-points 用小范围地点索引读取后聚合 |

三个方向分别完成独立 CR，未发现 P1/P2。功能未增加请求参数、响应字段、索引、结果缓存、后台任务或并发。前端无需修改。

**适用范围：** 有普通非空 q、locations 条件，搜索仅标准词、仅方言词或两者；没有省市精确筛选、分区、精确标准词条件等额外过滤。特殊 LIKE 通配符、关键词与地点文本重叠、默认四字段及其他组合保留原路径。`definition` 指标准词，`headword` 指方言词，`detail` 才是备注/详细信息字段。

**范围解析：** 最多枚举 257 个不同词条地点名，超过 256 个即回退；收集最多 257 个额外地点身份，超过 256 个也回退。地点名分支保留孤立词条；元信息分支保留 `(user_id, location_name)` 且排除前一分支覆盖的名字。解析结果在一次请求内复用，通过参数化 VALUES CTE 和现有两个地点索引读取词条，没有先收集全部词条 id。

**范围探测：** 预算 `min(32768, max(1024, 总词条数/10))`，最多访问预算+1 条索引候选来决定是否启用新路径。超预算回退原查询；32 个以上地点搜索项也回退。这些阈值只选择执行路径，不限制查询、聚合或返回条数。不同地点数量不能直接代表范围大小。

**entries 缓存：** 保留原 count SQL/参数作为缓存签名，只在已有 lazy miss 回调内规划；缓存命中、旧式 count loader 和第二页起不探测。规划、页与精确总数使用同一读 SAVEPOINT。standard-words / map-points 从规划到主 SELECT 启动也共享读快照，主 SELECT 游标继续保留快照；标准词仍逐行消费 SQL 分组。

## 2. 测量环境与数据

- 当前集 95,003 条；增长集 475,015 条，按分离用户身份扩展，地点名和词形保持不变；另有 95,003 条高命中合成集。数据库只读，没有在生产测试。文件哈希和行数保留在 JSON。
- 两类容器均限制 **2 CPU、2 GiB、无 swap、禁网**；核对 cpu.max / memory.max / memory.swap.max。串行执行，不推断并发吞吐容量。
- **原生 SQL：ARM Linux、SQLite 3.46.1**，回放最终代码实际产生的全部 SELECT，包括规划和精确计数；1 次预热后 7 轮交替执行，取中位数。它不含 Python 聚合、对象构建和事务控制语句的微小开销。
- **服务函数：Linux amd64 镜像在 Apple ARM 宿主模拟执行**，Python3.12 / SQLite3.46.1。调用真实 before/after 函数，包含范围解析、事务控制、标准词归一/排序、返回 dataclass 构建；每项每版本独立进程，5 次调用取中位数，首次耗时单独记录。没有 HTTP、鉴权、真实 Redis、网络、JSON 序列化或排队计时。
- 时间、RSS、tracemalloc 分开运行。共 **246 组服务配对：184 时间、61 RSS、1 heap**；另有 **184 组原生 SQL 配对**。原始 SQL、采样和进程 I/O 均保留，所有响应摘要一致，entries 额外读取无分页的完整有序结果验证 total。
- 没有清空宿主磁盘缓存；独立进程首次计时不是冷盘测试，5 次中位数也不等于上线首次 HTTP 请求耗时。架构模拟下的服务数字不能直接换算成生产延迟。

场景标记：small2=天柱竹林＋息烽；small8=条数最少的 8 个本地地点；large1=廣州白話；wide22=条数最多的 22 个地点，覆盖增长集约 95.6%。metadata=locations 中输入“廣西”，是地点元信息文字匹配，不是 province 参数精确筛选。下面均是各自同一轮 before/after 配对，不把原型轮次与正式轮次拼接比较。

## 3. entries：首页计数 miss

475,015 条数据：

| 场景 | 原生 SQL 前→后 ms | 服务函数前→后 ms（模拟架构） |
|---|---:|---:|
| small2-definition-蜘蛛 | 56.347→3.920 | 86.669→5.451 |
| small2-headword-人 | 57.458→3.831 | 86.713→5.680 |
| small2-definition+headword-蜘蛛 | 43.204→3.506 | 71.040→4.948 |
| small2-definition+headword-人 | 71.192→3.649 | 112.956→5.660 |
| small2-definition+headword-不存在词8f0b | 64.149→3.823 | 114.025→5.942 |
| small8-definition+headword-人 | 47.002→7.197 | 81.108→13.994 |
| metadata-definition+headword-蜘蛛 | 42.077→5.844 | 75.515→10.332 |
| large1-definition+headword-蜘蛛 | 70.265→73.631 | 117.072→119.402 |
| wide22-definition+headword-蜘蛛 | 54.586→58.061 | 100.410→105.474 |

两小地点、“蜘蛛”原生 SQL 43.204→3.506 ms（约 12.3 倍），服务函数 71.040→4.948 ms。“人”匹配 105 条，首页 50 条满页，仍精确计数；原生 SQL 71.192→3.649 ms（约 19.5 倍）。没有以省略 total 或减少匹配字段换速度。

当前 95,003 条：

| 场景 | 原生 SQL 前→后 ms | 服务函数前→后 ms（模拟架构） |
|---|---:|---:|
| small2-definition+headword-蜘蛛 | 8.096→0.864 | 14.219→1.402 |
| small2-definition+headword-人 | 8.431→0.939 | 14.263→1.564 |
| small8-definition+headword-人 | 10.065→2.178 | 18.645→4.157 |
| wide22-definition+headword-蜘蛛 | 8.273→9.218 | 16.523→19.582 |

范围很大时返回原计划，仍有探测成本。例如增长集 wide22 两字段“蜘蛛”54.586→58.061 ms，多约 3.48 ms（6.4%）；当前集 8.273→9.218 ms，多约 0.95 ms（11.4%）。不能说每个搜索都更快。

## 4. entries：计数 hit 已避开原型退化

在真实函数中提供精确缓存值，只测数据库和函数成本，不计 Redis 网络。实际 before/after 的 SQL 完全一致，且都没有规划 SQL：

| 场景 | 原生 SQL 前→后 ms | 服务函数前→后 ms（模拟架构） |
|---|---:|---:|
| small2-definition+headword-蜘蛛-count-hit | 43.694→44.061 | 72.584→70.735 |
| small2-definition+headword-人-count-hit | 27.267→27.078 | 43.022→43.766 |
| small8-definition+headword-人-count-hit | 1.344→1.344 | 3.059→3.051 |
| large1-definition+headword-人-count-hit | 1.678→1.697 | 3.422→3.439 |
| wide22-definition+headword-人-count-hit | 0.439→0.433 | 2.000→1.940 |

原型中“8 个小地点＋人”在计数 hit 时曾从约 1.5 退化到 11.6 ms，正式实现不走该路径。本次同条件原生 SQL 前后均约 1.344 ms，服务函数 3.059→3.051 ms；wide22“人”约 0.439→0.433 ms，变化属于波动。

保留原取页也意味着：某些稀少词在仅计数 hit、响应缓存 miss 时，仍可能扫描较多范围外记录。此次没有对 hit 路径承诺额外提速；响应缓存命中则沿用原有直接返回机制。

## 5. standard-words：小范围聚合

增长集，完整返回匹配归一词组：

| 场景 | 原生 SQL 前→后 ms | 服务函数前→后 ms（模拟架构） |
|---|---:|---:|
| small2-definition-蜘蛛 | 20.361→2.595 | 40.702→3.922 |
| small2-definition+headword-蜘蛛 | 52.262→3.059 | 101.614→4.166 |
| small2-definition+headword-人 | 52.787→2.988 | 106.315→4.221 |
| small2-definition+headword-不存在词8f0b | 52.605→3.392 | 113.972→4.918 |
| small8-definition+headword-人 | 120.509→5.721 | 253.377→9.229 |
| metadata-definition+headword-蜘蛛 | 35.731→4.679 | 71.470→7.635 |
| large1-definition+headword-蜘蛛 | 55.995→58.722 | 98.720→103.539 |
| wide22-definition+headword-蜘蛛 | 124.653→127.681 | 238.381→238.936 |

两小地点两字段“蜘蛛”原生 SQL 52.262→3.059 ms（约 17.1 倍），服务函数 101.614→4.166 ms。8 个小地点“人”SQL 120.509→5.721 ms，服务 253.377→9.229 ms。简繁归一、变体频次、地点去重、代表词选择、排序和 total 均保留。

**无 q 全量聚合没有再次优化。** 当前集完整返回 39,965 个归一词组，SQL 相同；服务中位数 268.475→265.752 ms、heap 峰值前后均约 25.076 MiB，视为基本不变。不同词组继续增长时，Python 分组和完整输出内存仍会增长；本轮只减少受限地点筛选时的扫描。

## 6. map-points：小范围分支

增长集，保留全部匹配地点、用户身份、总词条数、缺坐标统计、原 MIN(id) 顺序及展示元信息：

| 场景 | 原生 SQL 前→后 ms | 服务函数前→后 ms（模拟架构） |
|---|---:|---:|
| small2-definition-蜘蛛 | 52.709→2.548 | 103.896→3.732 |
| small2-definition+headword-蜘蛛 | 53.549→3.129 | 101.221→4.485 |
| small2-definition+headword-人 | 53.662→3.015 | 110.209→4.480 |
| small8-definition+headword-人 | 121.343→5.792 | 248.063→9.772 |
| metadata-definition+headword-蜘蛛 | 35.509→4.820 | 76.412→7.265 |
| large1-definition+headword-蜘蛛 | 56.138→59.384 | 99.102→100.344 |
| wide22-definition+headword-蜘蛛 | 136.074→141.180 | 238.694→237.191 |

两小地点两字段“蜘蛛”SQL 53.549→3.129 ms（约 17.1 倍），服务 101.221→4.485 ms。8 个小地点“人”SQL 121.343→5.792 ms，服务 248.063→9.772 ms。

大范围回退仍多出规划成本：wide22 两字段“蜘蛛”SQL 136.074→141.180 ms，多约 5.11 ms；服务中位数略降属于运行波动，不能据此说宽范围也得到优化。无 q 路径 SQL 不变。

## 7. 高命中与首次调用

95,003 条合成高命中集，q=共同，范围内几乎所有词条命中：

### items

| 场景 | 原生 SQL 前→后 ms | 服务函数前→后 ms（模拟架构） |
|---|---:|---:|
| small2-definition+headword-共同 | 27.742→0.958 | 49.833→1.621 |
| small8-definition+headword-共同 | 30.403→1.582 | 57.159→2.581 |
| large1-definition+headword-共同 | 10.999→12.005 | 20.287→21.396 |
| wide22-definition+headword-共同 | 20.045→20.941 | 37.919→40.003 |

### standard_words

| 场景 | 原生 SQL 前→后 ms | 服务函数前→后 ms（模拟架构） |
|---|---:|---:|
| small2-definition+headword-共同 | 11.338→1.507 | 24.290→4.781 |
| small8-definition+headword-共同 | 27.587→4.605 | 60.327→11.365 |
| large1-definition+headword-共同 | 32.682→33.022 | 202.098→212.197 |
| wide22-definition+headword-共同 | 79.521→78.540 | 369.748→374.153 |

### map_points

| 场景 | 原生 SQL 前→后 ms | 服务函数前→后 ms（模拟架构） |
|---|---:|---:|
| small2-definition+headword-共同 | 10.694→0.977 | 21.451→1.665 |
| small8-definition+headword-共同 | 25.894→2.018 | 50.357→4.004 |
| large1-definition+headword-共同 | 11.006→11.829 | 21.029→22.341 |
| wide22-definition+headword-共同 | 25.510→26.486 | 52.764→55.599 |


高命中也能受益的前提是地点范围小。大地点/宽范围回退，因此没有套用“所有高命中词都适合某计划”的结论。

独立进程首次调用还包含初始化、SQL 编译、读页等成本，以下为服务函数原始首样本，不是生产容量预测：

| 增长集场景 | 首次 before→after ms | 5 次中位数 before→after ms |
|---|---:|---:|
| items / small2-definition+headword-蜘蛛 | 560.15→88.44 | 71.04→4.95 |
| items / small2-definition+headword-人 | 432.42→84.81 | 112.96→5.66 |
| standard_words / small2-definition+headword-蜘蛛 | 202.04→90.46 | 101.61→4.17 |
| map_points / small2-definition+headword-蜘蛛 | 197.60→89.04 | 101.22→4.48 |
| items / wide22-definition+headword-蜘蛛 | 274.30→356.78 | 100.41→105.47 |

## 8. 内存、I/O 和 2 核 2 GB 的边界

独立 RSS 进程，一次调用后读取 Linux VmHWM；不是完整 Gunicorn worker。时间进程跑 5 次及 tracemalloc 进程的峰值不混入本表：

| 增长集 / 两字段“蜘蛛” | before VmHWM MiB | after VmHWM MiB |
|---|---:|---:|
| items / small2 | 75.93 | 76.12 |
| standard_words / small2 | 76.01 | 76.11 |
| map_points / small2 | 76.04 | 76.12 |

典型变化不到 1 MiB，主要收益是提速，不能宣称有显著 RAM 降幅。缓冲的记录数有上限，但单条字符串大小及完整响应仍影响内存，不能仅凭 256 条的限制承诺固定字节数。

- 服务测量整批 cgroup 峰值 291.5 MiB；原生 SQL 回放整批 247.4 MiB，均 OOM=0。包含父进程、冻结 SQL、结果校验等，不是单请求内存或生产 worker 容量预测。
- 独立 RSS 模式进程单次查询的非零 write_bytes 出现在高命中标准词大地点/宽范围：before/after 分别同为 **1,478,656 / 2,768,896 字节**。time 模式每项执行 5 次，累计分别为 7,393,280 / 13,844,480 字节，前后也相等。本批未观察到新增写入量；这是进程 I/O，不能精确归属某个临时文件。SQLite 原有 GROUP BY / ORDER BY 临时空间仍可能存在，没有应用磁盘聚合，没有 temp_store/config/schema 改动。
- 现有单机跨 worker heavy=2、expensive=1、等待名额和 30 秒 admission 等待预算不变，没有增加进程/线程/后台任务；已接纳查询没有新增执行时限或自动重试。
- 规划中的地点元信息匹配仍可能扫描地点表，返回缓冲有界不等于全程 I/O 恒定。超过 256 个不同词条地点名时此优化回退，速度回到原路径；没有用增长场景掩盖这一能力边界。
- 普通 B-tree 仍不能直接定位任意子串。默认四字段、省市/分区复杂组合、通配符、无地点、无 q 和深分页等未扩大适用范围。没有对所有分支承诺同一提速倍数。

## 9. 回归与独立审查

最新 vocabulary 全量：**599 passed、6 failed（11.72 秒）**。六失败均在基线 `b8d90fe` 独立复现，不是本轮引入；没有把全套描述为全部通过。

| 六个既有失败 | 问题 |
|---|---|
| routes::test_vocabulary_search_api_config_is_public_but_rate_limited | 既有限流配置与预期不一致 |
| service::test_import_upload_accepts_real_docx_whitespace_mode | 既有 DOCX 解析 |
| service::test_query_vocabulary_items_searches_content_fields_and_paginates | 既有 DESC 排序预期 |
| service::test_query_vocabulary_items_searches_simplified_and_traditional_variants | 既有结果顺序预期 |
| service::test_query_vocabulary_map_points_aggregates_locations_without_pagination | 测试期望不存在的 location_label |
| service::test_query_vocabulary_location_options_returns_distinct_public_names | 既有地点标签分隔符预期 |

新增/更新验证包含：

- 名字与元信息重叠、孤立地点、同名不同用户、简繁词形、无命中、精确 total、满页/不足页、全页顺序；32/33 参数、257 名字、257 额外身份及宽范围回退。
- **5,001 个标准词组**完整输出与旧路径相等；**700 个同名不同用户地图点**完整输出与旧路径相等。
- WAL 写入发生在规划与主查询之间仍读取同一快照；调用方事务不被提交，规划/查询异常正确清理读 SAVEPOINT。
- 真实 Redis＋HTTP：首次小范围请求规划一次；改变 page_size 让响应缓存 miss 后，独立 total 缓存命中，未再次规划且响应内容一致。
- 246 组服务响应摘要相等，entries 的完整有序匹配行与精确 total 相等；184 组原生 SQL 结果相等，规划和主 COUNT 均计入时间。

代码三方向、测量工具及缓存集成测试已独立 CR，无 P1/P2。基准保存并核对最终 query.py / scope_plan.py 哈希；测量工具后续加入执行前后强制哈希检查，避免复现时工作区构件漂移。该检查位于父进程、计时之外，不改变本批所测查询。

## 10. 复核资料与后续

- [全部 184 场景 CSV](vocabulary-scoped-release-2026-11-01.csv)：原生 SQL、服务中位数/首次耗时、61 项独立内存、总数/返回数。
- [采样与资源 JSON](vocabulary-scoped-release-2026-11-01.json)：源文件和数据哈希、全部采样、进程 I/O、响应摘要、cgroup 信息。冻结 SQL 完整原始资料在本地 outputs/vocabulary-scoped-release-20261101/。
- [真实代码基准工具](../scripts/benchmark_vocabulary_scope_release.py)、[实施计划](plans/2026-11-01-vocabulary-scoped-release.md)。工具从已跟踪的探索报告读取固定场景，避免依赖未跟踪的旧原型输出。

本地复现：准备上一轮离线 fixtures（benchmark_vocabulary_release.py --prepare）；运行本工具 --prepare；将工作区只读挂载，仅输出目录可写，在受限 amd64 应用镜像执行 --batch --rounds 5；再在原生 ARM Python3.12 镜像执行 --native-sql --source service.json --rounds 7。两容器均使用 --cpus 2 --memory 2g --memory-swap 2g --network none，数据库始终 mode=ro。禁止在服务器运行此基准。

本轮适合保留：小范围、冷计数的显著收益，以及聚合的少扫描路径。下一步若继续优化，应单独研究宽范围探测成本、计数 hit 的稀少词取页，以及默认多字段/行政区组合；仍需实测后再扩大选择条件。无 q 的全量标准词内存增长是另一个问题，本轮没有靠缩减返回或增加缓存解决它。
