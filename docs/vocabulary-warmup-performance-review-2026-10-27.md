# 词表预热性能审查（2026-10-27）

基线业务代码：`820e177`。前文记录修复前审查、离线测量和隔离原型；用户批准后的业务修复、真实Redis测量见末节。新增复现脚本 `scripts/benchmark_vocabulary_warmup.py`，不增加索引、结果缓存或常驻服务。

## 预热到底做什么

`cache.py:DEFAULTS` 固定7份默认结果：总词条数、不同地点名称数、地点选项、entries第一页50条、全量map-points、standard-words前1000和前100项。不会预热模糊关键词、其他筛选条件、其他分页或所有标准词。完整查询能力未被这些固定预热参数限制。

`cache_warmup.py:warm_once` 使用数据库级Redis租约，跨worker最多一个预热执行者，七份结果串行处理。先生成1000项，再复用前100项，已经避免同一轮聚合两次。查库使用现有run_bounded，不直接阻塞事件循环，但CPU和GIL竞争仍然存在。

WEB模式启动时，在lifespan yield前等待默认预热完成；其他worker拿不到租约会每1秒等待。运行中写入触发后台预热，事件后等待1秒合并；锁竞争/版本变化后约1秒重查，异常退避5、15、60秒；正常缺失检查每60秒一次。数据版本变化时不发布到新版本，但已经开始的旧聚合不会被强杀，可能消耗一轮过时计算。

当前地点修订参与全部SEARCH_KINDS缓存版本，所以地点变化会使地点选项、entries、map-points、两个standard-words默认结果重新生成，两份纯计数缓存继续命中。这与早期设计文档中“地点变化仅重建地图”的描述不同；不能按旧文档估计实际工作量。查询响应包含地点元信息，直接缩小失效范围需要逐字段验证。

## 方法与边界

本机macOS，项目虚拟环境，SQLite 3.53.2；真实库只读。未发现可用Redis测试服务，16379连接失败，因此使用明确标注的内存Redis替身，执行真实warm_once、acall/store、SQL、对象转换、JSON编码、现有准入及sleep。替身不模拟Redis网络延迟、全库SCAN清理、Lua成本、TTL、淘汰及并发一致性，不可作为生产完整预热耗时或真实Redis集成测试。

计时为顺序运行5轮中位数；数据库页已热，不是操作系统冷盘启动测试。增长库只作可删除的离线夹具。每次验证7份缓存均存在；隔离调度候选还逐字段比较7份缓存内容与原实现一致。标准词另做limit=None全量对比，确认预热前1000项与完整结果前1000项相同、total相同，完整结果不截断。

| 夹具 | 词条 | 不同原始词形 | 地点名称 | 完整归一组 |
| --- | ---: | ---: | ---: | ---: |
| 当前 | 95,003 | 41,558 | 29 | 39,965 |
| 十倍复制，词形/地名不变 | 950,030 | 41,558 | 29 | 39,965 |
| 三倍复制，增加词形/地名 | 285,009 | 143,486 | 87 | 140,637 |

## 速度

离线完整冷缓存预热（含固定sleep，不含Redis/清理）约0.936s、1.099s、1.415s。只缺map-points时仍约0.746s、0.805s、0.765s。缓存全部齐全的离线检查约0.4ms；真实实现仍会先cleanup，不能据此说线上健康检查只要0.4ms。

下表仅为各同步服务计算中位数，单位ms，不含sleep/Redis/准入等待：

| 步骤 | 当前 | 95万、词形不变 | 28.5万、词形增长 |
| --- | ---: | ---: | ---: |
| 总词条数 | 0.055 | 3.547 | 1.388 |
| DISTINCT地点名称数 | 0.038 | 0.044 | 0.053 |
| 地点选项 | 0.094 | 0.415 | 0.246 |
| entries第一页（含精确计数） | 0.555 | 7.817 | 2.439 |
| 全量map-points | 3.308 | 37.722 | 11.646 |
| standard-words前1000 | 133.058 | 197.555 | 606.261 |

两份计数已经很便宜，不值得作为首要优化对象。标准词是主要计算瓶颈，增长取决于不同词形、归一组、词—地点组合，而不只是行数。普通B-tree已用于默认分组；只替换SQL索引不能消除Python全量归一和排名。

当前标准词1000项JSON编码约5.14ms，UTF-8约103,296字节；词形增长夹具约5.35ms、123,655字节。1000项复用为100项时还会再次jsonable_encoder。此重复转换确实存在，但本次只有几毫秒，优先级低于等待、清理及全量聚合。七份永久默认结果不受按需缓存128KiB限制，不能假定永久缓存大小恒定。

## 主要瓶颈和建议

### 1. 命中缓存也固定等待100ms

for循环每项末尾都会sleep，包含命中缓存、复用100项及最后一项。一轮名义上固定700ms。只丢一个小缓存也绕全部7项并等待，补齐远慢于实际SQL。

隔离原型仅改为“实际查库后才sleep”，保留原SQL、1000/100复用、串行和现有并发上限：

| 当前库 | 原实现ms | 隔离候选ms |
| --- | ---: | ---: |
| 全部缺失 | 936.33 | 816.49 |
| 仅地图缺失 | 746.27 | 114.44 |
| 地点版本变化 | 931.55 | 607.48 |

候选与原实现是分批测量，不是同轮交替；主要收益对应明确消除的sleep，不能把这些比例推广为生产承诺。建议优先实施：命中项跳过无效间隔，只在实际重查询之间让出；最后一项不再无条件sleep。处理仅100项缺失时必须复用已有1000项，不能因跳过1000项而重新聚合。不得为了缩短预热时间改成七路并发。

### 2. 健康检查也先扫描Redis清理

warm_once在ready检查前调用cleanup。cleanup对default、ondemand各调用scan_iter，即遍历整个Redis键空间再MATCH词表前缀，并对匹配key逐个EVAL。SCAN是增量命令，但scan_iter循环最终会走完整个遍历；COUNT=32不是整轮只检查32项。

Redis还服务其他模块，因此成本取决于全库key规模、旧版本积压和网络往返，不只是词表当前最多128个按需key。每个worker每60秒都可能取得全局锁后做这一遍；锁避免同时执行，不能避免先后重复。刚完成启动预热，_run还会立即再检查一次。

建议将“缺失检查”与“旧版本清理”分开计时、限频；复用现有串行任务/全局租约，每轮限制SCAN步数及清理命令量，保留游标逐轮推进。缺失检查可优先进行，旧版本永久key仍须最终清理，不能简单删除cleanup或让ready后永远跳过清理。按需Lua写入和版本校验保持原语义。未测真实Redis，尚无可引用的节省毫秒数。

### 3. 标准词全量归一、分组和排名

limit=1000只限制最终结果，不限制进入Python的词—地点分组。每种原始词形仍需归一、记录计数和地点集合，最终对全部归一组评分。8192项归一缓存有界，但全库扫描不同词形远超容量，不能指望重复预热时所有转换命中；本轮profile观察到41,558次转换。

不能简单把SQL加LIMIT 1000：简繁词形可能合并，排名按地点数/条目数等计算，提前截断会改变结果和total。保持当前1000/100共算；下一阶段若优化归一/分组对象，应先验证完整结果并测不同词形增长，不扩大标准词缓存，不预设纯SQL还有倍数收益。

### 4. 后台预热与在线请求争资源

预热虽串行且在线程里，仍占一个heavy槽；标准词还占唯一expensive槽，会与在线standard-words/map-items竞争。共享上限为2 heavy、1 expensive、8 waiter、30秒准入预算；没有新增执行超时。缓存编码在_load的run_bounded返回后进行，并非全部由查询槽覆盖，当前1000项编码较小，但不能把线程池视作零成本。

独立本机并发实验：在预热进入标准词计算时，发起一个默认字段q=什么的entries服务层探针，共5轮，保留现有槽位：

| 数据 | 单独查询中位数ms | 与预热同时ms |
| --- | ---: | ---: |
| 当前 | 39.39 | 73.25 |
| 词形增长 | 117.85 | 152.11 |

5ms周期事件循环探针的每轮最大额外延迟：当前约9.2–12.2ms，词形增长约19.9–38.7ms。此实验没有HTTP、Redis或2核限制，只说明移到线程后仍有CPU/GIL竞争，不是生产并发容量预测。

建议后台预热拿不到现有资源时退让、合并到最新版本后稍后尝试，避免占据在线等待队列；不增加槽位/worker，不创建并行重试。启动期和运行期采用不同调度预算，在线高峰保留重查询之间的让出。不能保证一直繁忙时立即预热完成；用户请求仍走现有同key合并和准入路径。若持续写入，应比较开始重聚合前等待稳定窗口的收益，保留防饥饿上限，不强杀已执行线程。

## 内存资源

独立启用tracemalloc运行真实离线warm_once，不与计时共用。当前Python分配峰值31.84MiB，词形增长108.07MiB。进程生命周期RSS峰值分别152.28MiB、335.38MiB，包含导入、SQLite、tracemalloc自身以及增长夹具生成历史，不是纯查询RSS增量或生产worker预算。测量CPU时间也受tracemalloc明显影响，不能与无追踪计时混用。

即使只预热1000项，临时聚合仍随全部不同归一组增长。这是2GB服务器长期的主要风险；本轮不提出磁盘聚合，不新增常驻全量缓存，也不承诺固定内存。全量接口仍应返回所有结果。

## 验证与复现

`tests/test_vocabulary_cache_lifecycle.py tests/test_vocabulary_cache.py`：4通过、17因无Redis跳过；不能声称Redis集成已通过。脚本py_compile通过，业务文件未改。

```sh
_RUN_TYPE=MINE .venv/bin/python scripts/benchmark_vocabulary_warmup.py --rounds 5 --output /tmp/vocabulary-warmup-current.json
_RUN_TYPE=MINE .venv/bin/python scripts/benchmark_vocabulary_warmup.py --scale 10 --rounds 5 --output /tmp/vocabulary-warmup-growth.json
_RUN_TYPE=MINE .venv/bin/python scripts/benchmark_vocabulary_warmup.py --scale 3 --distinct --rounds 5 --output /tmp/vocabulary-warmup-distinct.json
_RUN_TYPE=MINE .venv/bin/python scripts/benchmark_vocabulary_warmup.py --baseline 820e177 --pause-only-after-query --rounds 5 --output /tmp/vocabulary-warmup-candidate.json
_RUN_TYPE=MINE .venv/bin/python scripts/benchmark_vocabulary_warmup.py --resource --output /tmp/vocabulary-warmup-resource-current.json
_RUN_TYPE=MINE .venv/bin/python scripts/benchmark_vocabulary_warmup.py --resource --scale 3 --distinct --output /tmp/vocabulary-warmup-resource-distinct.json
_RUN_TYPE=MINE .venv/bin/python scripts/benchmark_vocabulary_warmup.py --interference --rounds 5 --output /tmp/vocabulary-warmup-interference-current.json
_RUN_TYPE=MINE .venv/bin/python scripts/benchmark_vocabulary_warmup.py --interference --scale 3 --distinct --rounds 5 --output /tmp/vocabulary-warmup-interference-distinct.json
```

推荐实施顺序：先去掉命中项的无效等待，再限频/分步清理Redis，随后改进后台资源退让；最后研究标准词归一聚合的更大改动。完整生产速度还需要在同机Redis和实际2核2GB机器测一次冷缓存、齐全检查、失效重建、并发请求及MEMORY USAGE，不能用上述离线秒数替代。


## 用户批准后的修复与真实Redis验证

### 最终实现

- `cache_warmup.py`：只在相邻真实查库之间等待100ms。缓存命中、100项复用及末尾不额外等待；仅当100项缺失时才转换1000项对象。等待后复核数据版本/预热租约，过时则停止后续查询。
- `cache.py`：旧key清理每轮至多两次SCAN（每类一次），使用pipeline处理返回页；Redis记录两个游标及pending状态，共享门控。未完成时约1秒后推进，完成后60秒限频。COUNT=32仍只是提示，不宣称严格32-key上限或固定页内存。
- 清理在本轮查询工作结束后的finally推进，包含缓存已齐全、后台繁忙、版本变化和异常退出的路径。游标只在删除命令成功且gate token仍属于当前持有者时提交；失败释放gate以便重试，丢失gate不提交。写入切版本与解除旧清理冷却在同一Redis事务，避免新版本旧key长时间等待。
- `resources.py`：后台一次性尝试现有heavy/expensive槽，不占8个在线waiter名额；计算key已由在线请求持有也立即退让。未完成由原串行调度器约1秒后合并重试；Redis等异常仍按5/15/60秒退避。启动仍走原等待路径。不是严格优先级调度，繁忙时不保证立刻补齐。
- 2 heavy、1 expensive、在线30秒准入预算保持不变；已接受SQL取消时仍等待线程结束再释放槽和租约。没有新增SQL执行超时、并行查询、全量ID集合、应用磁盘聚合或标准词结果缓存。

前端只读核对：`dialects-vue-frontend/project/src/main/views/explore/word/vocabulary/VocabularyViewPage.vue:600` 定义 `STANDARD_WORD_OPTIONS_LIMIT = 1000`，1409行的参数构造函数将它传给standard-words接口。后端HTTP默认100项。因此预热保留1000/100两份固定结果；不会把前端改成100项，也不会限制limit=None完整结果。

标准词聚合算法没有改变：仍需归一和统计全部候选，最后选择前1000项。不能通过提前SQL LIMIT保持同样排名、简繁合并和精确total。

### 真实Redis对比

本机Docker已有Redis 8镜像，启动了仅绑定localhost随机端口、限制1CPU/192MiB容器内存、128MiB Redis maxmemory且关闭持久化的临时测试实例。未改共享Redis配置，不触碰其他模块数据；每轮使用独立命名空间，结束后删除。SQLite仍在本机运行，数据页预热；5轮中位数。旧版加载`820e177`的cache/warmup模块，SQL查询代码相同；两个版本分批测量，未交替。

| 当前95,003条 | 旧版ms | 修复后ms |
| --- | ---: | ---: |
| 全部默认缓存缺失 | 989.57 | 782.26 |
| 全部齐全 | 6.09 | 2.51 |
| 只缺地图 | 783.95 | 18.91 |
| 地点版本变化 | 984.52 | 533.39 |

| 词形增长285,009条、143,486种词形 | 旧版ms | 修复后ms |
| --- | ---: | ---: |
| 全部默认缓存缺失 | 1455.42 | 1273.14 |
| 全部齐全 | 7.89 | 2.56 |
| 只缺地图 | 804.97 | 33.38 |
| 地点版本变化 | 1458.88 | 1063.00 |

前后所有场景七份缓存内容的SHA256集合完全一致；完整归一组分别39,965和140,637，limit=None返回全部，前1000项与预热相同。速度改善主要来自去掉无效间隔、延迟对象转换和清理限频，不代表标准词归一聚合本身提速。不是生产2核2GB、冷盘启动、生产Redis键规模或并发容量保证。

14项新调度测试覆盖间隔数量、100项复用、真实Redis多页删除与新key保护、跨实例限频、失败不推进游标、失效/丢gate、忙时清理推进、后台不进在线队列、同key忙时退让，以及资源部分取得后的释放。另将已有SQL取消测试参数化，验证后台/在线两条路径。新调度、资源及生命周期24项通过；全vocabulary为411通过、10失败，失败均为既有预期差异：6项先前已知，另4项Redis集成仍预期地点变化仅影响地图，与此前实际SEARCH_KINDS版本范围不符。已在820e177原四个模块上重新复现相同10项。排除这10项后，vocabulary及共享toponyms资源回归422项通过、10项排除，无跳过项。独立代码审查未发现阻断问题。

真实Redis复现（必须指定可删除测试实例，禁止指向生产）：

```sh
_RUN_TYPE=MINE .venv/bin/python scripts/benchmark_vocabulary_warmup.py --redis-url redis://127.0.0.1:16379/0 --baseline 820e177 --rounds 5 --output /tmp/warmup-before.json
_RUN_TYPE=MINE .venv/bin/python scripts/benchmark_vocabulary_warmup.py --redis-url redis://127.0.0.1:16379/0 --rounds 5 --output /tmp/warmup-after.json
```

增长实验增加`--scale 3 --distinct`。原始结果`/tmp/vocabulary-warmup-real-before-{current,distinct}.json`及`/tmp/vocabulary-warmup-real-final-after-{current,distinct}.json`；真实Redis集成使用隔离临时实例，任务结束后停止删除，不留下新常驻服务。本轮业务改动按用户后续指令提交。
