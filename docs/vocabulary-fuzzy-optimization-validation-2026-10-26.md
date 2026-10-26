# Vocabulary 模糊搜索优化验证（2026-10-26）

本轮先优化 `search/entries`，再优化 `standard-words`。改动仅涉及后端 SQL 计划选择，不改前端、字段、排序、精确 total、简繁转换及 LIKE 通配符语义。不增加数量截断，不增加标准词缓存、数据库索引、常驻服务或应用临时磁盘聚合。

## 落地范围

基线：`20bf8f8`。生产改动：`app/service/vocabulary/query.py`。

- entries：默认内容搜索字段、非空关键词、单个地点文本筛选，且没有省/市/地区或精确标准词条件时，优先检查地点范围；精确计数使用既有 `idx_vocabulary_entries_user_location`。分页查询保留自己的自动计划，不强制跟随计数索引。
- standard-words：默认内容字段的关键词＋地点文本筛选使用该身份索引；此处实测支持多地点。
- 关键词、地点含 `%`、`_`、NUL，或关键词简繁变体与地点文本存在互相包含关系时，保留原计划。单字段搜索、地点元信息搜索、省市地区组合等原有分支不统一替换。
- 共享过滤器的地点优先选项默认关闭；map-points/map-items 不启用新路径。
- 不是用普通索引定位任意子串：身份索引仍需扫描，但可以在读取宽内容字段前排除范围外词条。standard-words 同时避免原计划按全部词形顺序进行大量内容回表。

已有的计数缓存、计数为零/越界短路、分页后关联地点继续保留。本轮不把这些既有收益重新计入。

## 测量方法

本机 macOS、项目虚拟环境、SQLite，单进程顺序调用服务函数。每组先预热，再旧/新交替测量 7 轮，表中为中位数（ms）。使用只读真实库及复制生成的独立测试库，未修改原数据。不是 Linux 2核2GB 生产容量、并发或端到端 HTTP 测试。

三组数据：

| 场景 | 词条数 | 不同原始词形 | 地点名称数 |
| --- | ---: | ---: | ---: |
| 当前库 | 95,003 | 41,558 | 29 |
| 十倍复制，词形与地名不变 | 950,030 | 41,558 | 29 |
| 三倍复制，并增加不同词形与地名 | 285,009 | 143,486 | 87 |

entries 表格为精确计数未命中缓存时的完整服务调用；另测了模拟计数命中，未把 Python 字典模拟命中当成真实 Redis 延迟。standard-words 全部使用 `limit=None`。测试夹具复制了现有分布，不能覆盖未来所有真实分布。

### entries

| 搜索条件 | 当前库：旧→新 | 95万：旧→新 | 词形增长：旧→新 |
| --- | ---: | ---: | ---: |
| 什么，无地点筛选 | 39.34→39.65 | 367.39→368.48 | 118.65→119.05 |
| 什么＋廣州 | 40.25→32.42 | 370.20→304.24 | 119.69→97.74 |
| 什么＋貴州 | 71.63→15.73 | 615.83→145.10 | 228.48→54.63 |
| 什么＋不存在地点 | 35.87→4.92 | 363.94→50.05 | 114.62→16.67 |
| 什么＋廣州/香港多选 | 40.48→40.47 | 368.88→368.53 | 120.03→120.41 |
| 人＋廣州 | 20.75→18.67 | 196.42→181.94 | 64.11→58.81 |

95万场景中，“什么＋廣州”降低约17.8%，“什么＋貴州”约76.4%，地点无命中约86.2%。不带地点的模糊扫描没有实质改善；多地点保留原路径。收益随关键词和地点选择率显著变化。

### standard-words（无限量返回）

| 搜索条件 | 当前库：旧→新 | 95万：旧→新 | 词形增长：旧→新 |
| --- | ---: | ---: | ---: |
| 什么，无地点筛选 | 37.49→37.39 | 371.79→370.69 | 121.22→122.79 |
| 什么＋廣州 | 79.39→30.94 | 894.43→302.67 | 286.97→107.73 |
| 什么＋貴州 | 77.79→7.20 | 899.94→81.86 | 263.65→25.49 |
| 什么＋不存在地点 | 77.55→5.08 | 909.26→51.07 | 253.98→16.95 |
| 什么＋廣州/香港多选 | 80.87→35.32 | 896.80→342.15 | 261.68→111.68 |
| 人＋廣州 | 80.23→39.35 | 778.24→226.07 | 324.38→165.64 |

95万场景中，“什么＋廣州”降低约66.2%，“什么＋貴州”约90.9%，地点无命中约94.4%。全部分组仍需要归一、统计和排序；本轮没有消除高命中时随不同归一词组增长的内存成本。

## 被舍弃或收窄的候选

- 全局调整条件顺序、去掉部分 COALESCE：收益不稳定，未采用。
- `instr` 预筛选后再执行原 LIKE：稀有词有收益，但人工100%命中计数出现约47%回退，未采用。未替换 LIKE 匹配语义。
- entries 多地点新路径：词形增长实验约186→217ms，故保留原计划。
- standard-words 关键词与地点文本重叠：增长实验约846→939ms，故加入保守回退；最终“新增＋新增”复测约653.14→653.70ms。entries 对应约39.92→40.01ms。
- 深分页窄ID方案按用户要求延后，不为本轮模糊搜索增加复杂度。

文本重叠守卫是保守启用条件，不能保证任意未来数据分布都不回退；后续应继续用真实慢条件测量，不能把索引提示扩大为所有模糊搜索的统一方案。

## 独立进程资源测量

另起进程分别运行旧/新版本，查询“人＋廣州”，启用 tracemalloc；资源运行不与上述计时混用。RSS 是包含导入、SQLite 和响应对象的进程生命周期峰值；Python分配峰值不含 SQLite 内部分配。每项一次，不能据此推导并发容量或固定内存上限。

| 数据/接口 | 返回数量 | 峰值RSS MiB：旧→新 | 查询Python峰值 MiB：旧→新 | 查询CPU秒（用户＋系统）：旧→新 |
| --- | ---: | ---: | ---: | ---: |
| 当前/entries | 50（total=9,277） | 64.44→64.48 | 0.08871→0.08876 | 0.0244→0.0219 |
| 当前/standard-words | 全部6,979组 | 79.02→79.25 | 6.67845→6.67849 | 0.1948→0.1500 |
| 词形增长/entries | 50（total=27,831） | 64.30→64.45 | 0.08985→0.08991 | 0.0662→0.0612 |
| 词形增长/standard-words | 全部20,937组 | 103.67→105.61 | 19.08569→19.08573 | 0.6185→0.4675 |

Python分配基本相同；词形增长时 standard-words 的单次RSS峰值增加约1.94MiB，不能宣称内存更低。SQL GROUP BY 可能使用 SQLite 内部临时B-tree。此平台 rusage 块读写计数均为0，不能据此断言无磁盘I/O、无内部临时文件；未做Linux磁盘临时量测量。

线上并发配置不变：2个heavy槽、1个expensive槽、8个等待名额、30秒准入等待预算。没有新增线程、执行超时或自动重试。标准词分组/完整响应仍随结果增长，不新增全量ID集合或无限缓存。SQL失败沿用现有异常处理，不自动执行另一条全量SQL重试。未在2GB机器上做双请求竞争压测，此项上线后仍需验证。

## 正确性与回归

- 新增47项测试：计划边界、简繁重叠回退、通配符、NUL、一次性Iterable、跨用户同名地点/孤立词条、精确计数复用、全页遍历和完整标准词结果比较。另增加1项HTTP响应契约场景。
- 基准每次核对服务响应的所有字段；entries 额外去除分页限制，以有界流式摘要比较全部匹配行及顺序，数量必须等于精确total。测试夹具通过API服务逐页遍历至越界页，检查所有页字段。standard-words 全量比较每组全部字段、顺序与total。
- 核心回归168项通过；vocabulary完整套件结果：359通过、41跳过、6失败。将相同6项在基线 `20bf8f8` 的query模块上重新执行，仍全部失败（已有配置限流、DOCX解析及展示格式预期问题）。排除该6项后359通过、41跳过。Redis等环境相关跳过项未视为已验证。
- `py_compile` 和 `git diff --check` 通过。独立代码复核未发现阻断问题。
- 最终简繁重叠守卫补丁后，重新核对三份已接受基准中的56项 SQL/参数展开快照，最终生成SQL逐字一致。因此上述耗时对应的查询未被最后守卫改变；另有新守卫回归测试。最终query.py SHA256：`34ecd89c39642bb6302591c166b3cfb609b22093b69a1d6b8fb94c542e1a81ef`。

原始本机会话结果位于 `/tmp/vocabulary-fuzzy-accepted-{current,growth,distinct}.json`；资源结果为 `/tmp/vocabulary-fuzzy-resources-{current,distinct}.json`；最终SQL复核为 `/tmp/vocabulary-fuzzy-final-sql-verification.json`。这些是本地临时验证产物，复现以脚本和本文方法为准。

## 复现

```sh
_RUN_TYPE=MINE .venv/bin/python scripts/benchmark_vocabulary_fuzzy_queries.py --baseline 20bf8f8 --rounds 7 --endpoints items standard_words --output /tmp/vocabulary-fuzzy-current.json
_RUN_TYPE=MINE .venv/bin/python scripts/benchmark_vocabulary_fuzzy_queries.py --baseline 20bf8f8 --scale 10 --rounds 7 --endpoints items standard_words --output /tmp/vocabulary-fuzzy-growth.json
_RUN_TYPE=MINE .venv/bin/python scripts/benchmark_vocabulary_fuzzy_queries.py --baseline 20bf8f8 --scale 3 --distinct --rounds 7 --endpoints items standard_words --output /tmp/vocabulary-fuzzy-distinct.json
_RUN_TYPE=MINE .venv/bin/python scripts/measure_vocabulary_fuzzy_resources.py --version before --endpoint standard_words --q 人 --locations 廣州 --trace
_RUN_TYPE=MINE .venv/bin/python scripts/measure_vocabulary_fuzzy_resources.py --version after --endpoint standard_words --q 人 --locations 廣州 --trace
_RUN_TYPE=MINE .venv/bin/python -m pytest tests/test_vocabulary_fuzzy_query_plans.py tests/test_vocabulary_conditional_sql.py tests/test_vocabulary_query_resources.py -q --disable-warnings
```

运行全部场景会比上述已接受子集更广；脚本记录版本、平台、SQL计划和每轮样本。增长库仅用于离线测试，退出后删除，不是线上请求的处理方案。

下一步真正尚未解决的是“不带地点范围的默认多字段任意子串扫描”。本轮原型没有找到稳定的纯表达式替换；若继续优化，应先按真实慢条件分解计数、字段命中分布及宽字段读取成本，再决定是否有新的代码级路径。不要在没有证据时承诺普通索引能直接定位 `%关键词%`。
