# Vocabulary Partitions Implementation Plan

> Follow test-driven-development and verification-before-completion; user authorized implementation in this session after writing the plan.

**Goal:** 支持词表任意层级分区筛选、分区返回和可复现性能评估。

**Architecture:** 在 vocabulary 查询构造器添加有界分区谓词，新增独立路径规范化/树服务；缓存搜索结果同时依赖 entries/locations 版本。沿用现有连接、线程和 Redis 服务。

**Tech Stack:** Python、FastAPI、SQLite、SQLAlchemy、Redis、pytest。

## 1. 基线与测试

- [x] 新增 `scripts/benchmark_vocabulary_partitions.py`，通过 git show 读取旧 query 模块，在同一 SQLite backup 快照上对照测量；结果只写 benchmark/。
- [x] 在 `tests/test_vocabulary_partitions.py` 写隔离 SQLite 和 HTTP 用例，确认旧实现因缺少参数/接口失败。
- [x] 在现有 cache 测试补充地点版本依赖及竞态用例，运行确认旧规则失败。

## 2. 查询和返回

- [x] 新建 `app/service/vocabulary/partitions.py` 实现 `normalize_regions(regions, region_mode)`、`partition_filter(regions, region_mode, alias='l')`、`query_vocabulary_partition_options(session, region_mode='yindian', parent=None)`，列名仅白名单；谓词形式 `(l.column = ? OR substr(l.column,1,?) = ?)`。
- [x] 修改 query.py 四个入口及共享 `_build_filter_clause` 接收 regions/region_mode。entries 的 SELECT、dataclass、转换器加入两套分区。location-options 在 SQL 过滤之后聚合同名地点完整分区集合。
- [x] schemas/vocabulary.py 添加响应字段及树响应；routes/vocabulary.py 传递参数、新增 tree GET，错误明确返回 400/404。
- [x] 执行 `.venv/bin/python -m pytest tests/test_vocabulary_partitions.py -q`，要求全部通过。

## 3. 缓存一致性

- [x] cache.py 规范化新参数；所有 search 类 cache scope 使用 entries/locations 版本，SQL 保持 entries；WRITE/CLEAN 使用相同 scope 判断，命名空间升级。
- [x] 保留七项 DEFAULTS，新增组合只按需缓存；测试修改地点分区后旧缓存不可读，旧版本计算不可写入新版本。
- [x] 执行词表全部测试和已有 partition 路径测试，真实 Redis 单独命名空间运行、不清空其他键。

## 4. 实测、审阅与交付

- [x] 同一快照比较旧/新服务函数，多轮交替计时，独立测内存、查询计划与真实 Redis 命中；如发现明显回归先优化再复测。
- [x] 更新 `docs/api/vocabulary.md`，新增性能报告 `docs/performance/2026-10-20-vocabulary-partitions.md`，包含运行命令、样本量、限制和数据。
- [x] 代码审阅，修复重要问题，再运行针对性测试及 `git diff --check`，核对实际改动与设计。

执行结果：实现、独立审阅和同快照性能评估完成。新功能及相关缓存/生命周期/公共分区测试 128 通过；完整回归 289 通过、8 项既有失败，旧模块对照已复现，详见性能报告。
