# Vocabulary Deferred Count Implementation Plan

**Goal:** 已批准的先返回列表、同 worker 延后精确计数，前端最小兼容。
**Architecture:** 显式 opt-in；有界 lookahead；复用 scalar cache；响应后非排队、有期限任务。
**Tech Stack:** FastAPI / Starlette BackgroundTasks / SQLite / Redis / Vue / pytest / Vitest。

按用户直接执行授权在当前 dev 顺序实施，使用 TDD 与逐步审查，不重复询问执行方式。

- [ ] 新增 tests/test_vocabulary_deferred_count.py 查询测试，运行 pytest 验证 defer_total 参数不存在的失败；实现 query.py 可空 total/has_more、lookahead、私有 count-only，保留旧路径。
- [ ] 新增 tests/test_vocabulary_deferred_routes.py HTTP/真实 Redis 测试及事件顺序测试；验证 red 后实现 deferred_count.py 后台任务、schema、路由 opt-in 和缓存 pending 跳过。使用本地隔离 Redis，不访问默认外部 Redis。
- [ ] 覆盖后台资源/锁竞争、旧版本、冷却、Redis 故障和 SQLite 期限，修复后运行所有新增及 vocabulary 回归；单独验证已有六项基线失败。
- [ ] 前端现有 tests/vocabularySearchEntrance.test.js 添加卡片与地图 pending 多页测试，先观察失败；最小修改 VocabularyViewPage.vue 与 api/main/vocabulary.js，运行相关 Vitest，审查后独立提交前端。
- [ ] 冻结实现源码，使用已有只读生产副本对照多字段、单字/多字、地点/全库、0/末页/高命中/缓存命中，至少七轮，比较首包和全部后台成本，核对内容、排序与精确总数。
- [ ] 独立代码审查与资源边界报告；完成相关回归和 diff --check；仅提交本任务代码/测试/报告；移除临时本地 Redis，不推送或部署。
