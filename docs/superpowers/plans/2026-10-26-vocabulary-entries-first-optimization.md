# Vocabulary entries 优先、standard-words 随后的优化方案

**Goal:** 优先降低 /api/vocabulary/search/entries 常用模糊搜索的耗时，再优化 standard-words 的关键词加地点条件，保持前端、匹配语义、精确统计和完整返回能力。

**Architecture:** 先建立分阶段测量，再分别为计数、分页和标准词聚合评估少量条件 SQL 路径；只有结果一致且实测有收益的候选进入业务代码。未知收益不预设强制索引；不每请求试跑多个计划。

**Tech Stack:** FastAPI、Python、SQLite、既有 SQLAlchemy Session、既有 Redis 计数缓存和跨 worker 准入。

状态：本轮收窄后的模糊搜索优化及本机验证已完成，用户已要求提交。用户进一步明确：优先模糊搜索；深分页不作为本轮优化目标。先评估 entries，再评估 standard-words；最终共用同一 SQL 守卫。详细结果见 [验证报告](../../vocabulary-fuzzy-optimization-validation-2026-10-26.md)。

以下保留原始候选与验证清单，并不表示全部候选均需实施。最终范围和未验证事项以文末执行结论为准。

## 约束与范围

- 生产2核2GB；不加worker、线程配额、常驻服务、常驻词条ID集合或标准词缓存。
- 不采用应用临时磁盘聚合、匹配ID落盘或响应文件；独立实验库是基准夹具，不是生产方案。SQLite普通排序可能使用内部临时B-tree，需要测量其资源成本，不能保证SQLite绝不使用临时磁盘。
- 保留默认全部搜索字段、简繁展开、任意子串和现有SQL通配符语义，不改成前缀搜索或估算total。
- 不加返回数量限制。entries保留现有page/page_size协议；完整验证必须逐页核对到最后一页，而非仅核对第一页。standard-words基准使用limit=None，完整比较全部归一组，现有HTTP参数不改。
- 保留现有计数缓存、修订失效、空结果/越界短路、适用条件下分页后关联地点。不把已完成的改动再次计作新收益。
- map-points与map-items不是本轮主动优化目标；修改共享过滤器时必须检查其完整结果、顺序和统计。

## 阶段一：entries（优先交付）

### 任务1：建立分阶段基线与正确性基准

文件：扩展 scripts/benchmark_vocabulary_entries.py；新增 tests/test_vocabulary_entries_query_plans.py；新增 docs/vocabulary-entries-optimization-validation-2026-10-26.md。

- [ ] 保存当前query.py和git版本、Python/SQLite版本、DDL、统计信息、执行计划；原数据库只读。
- [ ] 单独测精确计数、分页SQL读取、对象构建及整个服务调用。分别测整页缓存未命中且计数冷、仅计数热，以及真实Redis/HTTP可用环境下的端到端请求；模拟计数命中不冒充真实Redis耗时。
- [ ] 对每个条件旧/新交替至少7轮，记录样本、中位数、范围。服务/SQL计时不混入tracemalloc；RSS、Python分配、CPU、临时文件I/O另做独立运行。
- [ ] 测当前约9.5万条、约95万条复制增长，以及独立增加不同词形/地点名称的增长夹具，明确人工数据局限。测试单进程顺序运行，避免基准并行互相干扰。
- [ ] 条件分层：无筛选；默认多字段；definition/headword/pronunciation/detail单字段；location和内容+location混合字段；精确选词单/多选；上述条件与地点文本、省、市、地区叠加。
- [ ] 选择无命中、少量命中、大量命中；单字、多字、简繁、空白、%、_、多地点和矛盾省市条件。检查NULL、孤立词条、跨用户同名地点、一次性Iterable。
- [ ] 测第一页、中间页、深页、最后一页和越界页。深页按每个条件的实际total选择，避免把不存在的深页仅测成短路。
- [ ] 对每个实现比较精确total、所有字段、ID顺序、分页元信息。选代表性条件逐页遍历所有命中条目，通过流式摘要和逐页字段核对验证无遗漏/重复，不在Python中保存全量匹配ID。

此任务输出慢分支排名和“计数/取页”的耗时比例；尚无entries新一轮实测，不预先承诺提速百分比。

### 任务2：分别评估计数SQL和分页SQL

业务候选位置：app/service/vocabulary/query.py 的 _build_filter_clause、query_vocabulary_items；沿用 app/service/vocabulary/cache.py 中的 _count_loader，不增加缓存或新重试。

候选A：范围优先的精确计数，优先测试关键词+小范围地点/省市/地区。

- [ ] 在隔离原型中比较当前JOIN、地点身份子查询/半连接及现有索引选择；地点身份必须同时包含user_id和location_name。
- [ ] 检查范围外词条能否在读取宽内容字段前被排除。省市和地区必须在同一个地点身份上同时成立，不能拼接成错误的独立存在判断。
- [ ] 保留e.location_name匹配分支、内容与地点元信息的OR语义、NULL与通配符语义；地点范围大、精确选词和矛盾条件必须单独比较。
- [ ] 不把“身份索引扫描”说成“任意子串索引定位”；以EXPLAIN与实际访问成本判断，而非仅看SQL文字顺序。

候选B：窄ID分页，本轮暂不实施；保留为后续选项，深分页仅回归。

- [ ] 隔离比较“过滤、排序、分页阶段只选e.id，随后按ID读取宽词条与地点信息”与当前实现。
- [ ] 地点元信息参与过滤时，先在ID子查询完成必要JOIN和过滤，再LIMIT/OFFSET；不得先分页后筛选。外层显式ORDER BY e.id DESC。
- [ ] 保持现有唯一地点约束和LEFT JOIN孤立记录语义。只物化当前页ID，最多现有page_size的200项，禁止先取得全部匹配ID。
- [ ] 检查SQLite是否本来已延迟读取OFFSET跳过行；若当前执行计划已避免这些读取，候选可能无收益，不强行落地。

候选C：默认多字段模糊扫描的低成本优化。

- [ ] 精确计数与分页分别比较自动计划、合适的既有索引和顺序扫描；分页有ID排序，不能照搬计数或standard-words的NOT INDEXED提示。
- [ ] 在实际表结构确认NOT NULL后，评估standard_word/local_expression/ipa/location_name去掉COALESCE；notes/informations等可空列保持原语义。只在可重复收益足够时采用。
- [ ] 相同列/参数重复表达式可去重，但保留所有原有匹配字段和简繁变体。不同用户传参形式必须仍与缓存规范化及失效一致。

以下方案本轮不采用：COUNT(*) OVER()一律替换、全量ID物化、默认UNION全部搜索分支、把精确total改成估算、改游标分页协议。它们可能放大扫描/排序、内存或改变前端；只能有独立证据时重新评估。

### 任务3：结果回归与entries独立交付

- [ ] 对有明确收益的候选先增加能在旧实现失败的SQL资源/分支测试，再实施最小业务改动；结果测试不能只断言SQL字符串。
- [ ] 新/旧实现逐条件比较全部结果；分页遍历验证不丢记录、不重复；查询期间有写入时验证现有修订失效路径，不虚称Redis计数和SQLite分页是原子快照。
- [ ] 运行新增用例及 tests/test_vocabulary_query_resources.py、tests/test_vocabulary_conditional_sql.py，再运行相关vocabulary回归。区分已知基线失败、环境跳过和本次新增失败。
- [ ] 在同一矩阵中记录受益和回退；关键常用分支若中位数回退超过10%且绝对增加至少5ms，必须解释、缩小启用条件或舍弃候选，不能仅以平均值掩盖反例。
- [ ] 以典型慢分支降低20%作为优先落地目标，不是性能承诺或牺牲正确性的硬指标；微小变化若不超过噪声，不增加分支复杂度。
- [ ] 测两个heavy槽竞争时的延迟与峰值，不增加并发。2GB环境若可用则实测，否则清楚标为待生产验证；不得根据本机tracemalloc承诺生产RSS。
- [ ] 给出完整报告并形成独立entries提交；不推送、不改前端、不混入standard-words尚未验证的业务改动。

## 阶段二：standard-words（entries交付后）

### 任务4：验证关键词+地点计划并实施保守分支

文件：app/service/vocabulary/query.py；tests/test_vocabulary_conditional_sql.py；scripts/benchmark_vocabulary_conditional_sql.py；扩展 docs/vocabulary-next-optimization-review-2026-10-25.md 或新增独立验证报告。

- [ ] 使用阶段一后的实现为新基线，避免共享过滤器变化导致重复计算收益。
- [ ] 隔离比较自动计划、idx_vocabulary_entries_user_location和顺序扫描，优先q+locations。仅locations、q+location搜索字段、省市/地区组合单独评估，不统一替换。
- [ ] 完整测试limit=None，核对每组key、代表词、variants顺序、entry_count、location_count、整体排序及total。地点数保持现有按地点名称去重的语义，不改成按用户身份计数。
- [ ] 覆盖不同关键词字段、范围大小、通配符、简繁、孤立词条和跨用户同名地点；比较高命中分组排序的内存/临时I/O，不能只看稀有词速度。
- [ ] 仅把重复测量有收益的条件纳入分支；保持无关键词覆盖索引、既有地区身份索引和通配符回退，除非新基线证据支持改变。
- [ ] 验证后实施、回归并单独提交；不扩大8192项归一缓存，不增加标准词响应缓存或持久化归一列。

已知参考：上一轮95万条实验完整返回，“什么+广州”约902→307ms，“人+广州”772→220ms，地点文本无命中641→51ms。这是独立原型、本机服务层结果，不能当本轮最终实现或生产承诺。增长夹具未增加词形种类，仍需补不同词形增长。

## 资源和失败策略

- 沿用全机2个heavy槽、standard-words等1个expensive槽、8个准入等待名额及30秒准入预算；不新增已接受查询的执行超时或自动重试。
- 查询单元维持在线程中的现有有界调度，不在async事件循环中直接运行同步SQL或全量Python聚合。计数与取页不并行执行。
- 窄分页额外集合最多一页ID；不保存全量匹配项。SQLite子查询/排序以及标准词最终分组仍可能随候选量增长，实测并记录，不能宣称固定内存上限。
- SQL错误沿用现有异常路径；不在失败时自动重跑另一条全量SQL。新分支异常通过后续修订回退通用路径，不对每请求重复试跑。
- 不在高峰期对生产运行全量基准或ANALYZE/VACUUM。原数据库只读；受控增长夹具可删除，失败后清理。
- HTTP响应校验/编码、无效缓存编码、map-items低复制属于后续独立事项，本轮不混入以免扩大回归面。

## 最终交付和决策

先交付entries的逐分支耗时、结果回归、资源测量及有证据支持的代码，再交付standard-words。每份报告必须同时列出无收益、退化场景与环境限制。若entries代码级候选收益不足，应报告扫描下限及实际瓶颈；在用户另行确认后才研究新增索引或数据结构，不为完成优化目标而改变匹配/返回语义。

## 执行结论（2026-10-26）

- 已完成：默认多字段关键词＋地点文本的分支比较、最小SQL改动、47项新测试、1项HTTP契约场景、三种数据增长基准（每项7轮）、全量结果核对、独立进程RSS/Python分配/CPU测量、独立代码复核和相关套件回归。
- 实际文件为 `scripts/benchmark_vocabulary_fuzzy_queries.py`、`scripts/measure_vocabulary_fuzzy_resources.py`、`tests/test_vocabulary_fuzzy_query_plans.py`，替代原计划中的候选文件名；未修改前端。
- entries仅对单地点启用；standard-words允许多地点。关键词与地点重叠、通配符等保留原路径。未启用全局重排、instr预筛选或COALESCE替换，原因及性能反例见验证报告。
- standard-words的收益单独来自其索引计划，entries专属的条件重排选项默认关闭，没有把该重排计为standard-words收益。
- 未实施：窄ID深分页、新索引、标准词缓存、应用磁盘聚合。无地点模糊搜索没有实质提速，不宣称本轮解决所有分支。
- 验证边界：计数命中使用模拟加载器；真实Redis网络/并发失效、完整HTTP端到端性能、Linux2核2GB竞争容量和临时文件I/O仍未验证。现有事务一致性与准入策略保持原状，不声称新增快照保证。
- 套件全跑为359通过、41跳过、6既有失败；6项在旧query代码上重现。排除这6项后359通过。核心168项通过。按用户后续指令提交本轮改动，不推送。
