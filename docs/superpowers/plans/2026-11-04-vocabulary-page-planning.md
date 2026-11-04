# Vocabulary Page Planning Implementation Plan

**Goal:** 修复已批准的总数缓存/分页选路耦合、规划全库 COUNT 和真实多地点误回退。
**Architecture:** 每请求一次 lazy prepare；读 SAVEPOINT 包围规划、结果计数与分页；有界统计估计/候选探测，保留原缓存键和结果契约。
**Tech Stack:** Python / SQLite / SQLAlchemy / pytest / existing Redis cache.

按用户“开始解决”的授权在本会话顺序执行，单人自审，不创建子任务或部署。

- [ ] 在 tests/test_vocabulary_scope_plan.py 增加 cached total + later page 索引路径、零/越界无探测、snapshot 和廉价规模边界的失败测试；命令 `.venv/bin/python -m pytest tests/test_vocabulary_scope_plan.py -q`，确认对应断言失败。
- [ ] 修改 app/service/vocabulary/scope_plan.py：有统计时使用 `sqlite_stat1.stat` 首项，无统计时 `SELECT COUNT(*) FROM (SELECT 1 FROM vocabulary_entries LIMIT 4097)`，候选最多 budget+1，保留解析上限与完整结果回退。新增 entries 专用 65536/4 政策参数，聚合保持 32768/10。
- [ ] 修改 app/service/vocabulary/query.py：原 count SQL 键保持不变；一次 lazy prepare 独立于 count callback，scope 覆盖每页；cache zero/out-of-range 在 prepare 前返回；同一个 SAVEPOINT 保持规划/COUNT/page snapshot。保留旧 count loader 原行为，完整结果 cache 路径不改。
- [ ] 更新已改变的旧计划断言；增加真实 Redis count hit/响应 miss 后继续规划、total invalidation 回归；运行 scope/first-page/literal/aggregation 和 cache routes 测试。
- [ ] 冻结改前 query/scope 源于本地 ignored evidence。使用真实副本“路”p1–4、韭/文昌、全库词和宽范围控制对比；相同 SQL runtime/CPU/内存约束，至少七轮，结果内容排序完全相同；新增预算若有明显控制组退化则调整政策并重跑受影响组。
- [ ] 按实际结果自审、完成相关 vocabulary 全套回归，记录资源边界和限制到 docs；只提交本任务代码、测试和文档，不提交数据库/原始日志，不推送。
