# Vocabulary 首页快捷查询预热

已由用户确认：将首页“蜘蛛”和“蚯蚓”的默认组合加入永久缓存与主动预热，在 dev 实施。

1. 用真实 Redis 和临时 SQLite 验证无需 HTTP 访问即可准备结果、TTL=-1、按需淘汰不影响永久结果，以及 entries/locations 变更后的刷新。
2. 在 `cache.py` 的 DEFAULTS 追加蜘蛛 entries（q=蜘蛛、search_fields=definition/headword、page=1、page_size=50）和蚯蚓 map-items（standard_words=蚯蚓、q 为空）。其他筛选组合仍按需缓存。
3. 在 `cache_warmup.py` 接入 map-items loader 并执行新增默认项，沿用全局串行租约、100 ms 查询间隔和后台让出策略。map-items 沿用在线查询的 expensive 资源槽；不新增 worker、线程池或服务。
4. 更新固定结果数量与查询间隔断言，运行缓存、调度、取消和资源限制测试；识别实施前已有失败。
5. 本地 95,003 条真实词表以只读 SQLite、隔离 Redis namespace 测量原七项和新增九项的预热耗时、Redis MEMORY USAGE、RSS 峰值；记录环境和局限，不将开发机结果当作生产承诺。
6. 更新 API 文档，只提交本次文件，保留已有无关工作；关闭临时测试 Redis。

地点变更沿用当前实现：全部 SEARCH_KINDS 均依赖 locations 版本，故新增两项无需另建失效机制；entries 变更仍更新全部结果。默认结果由七份变九份，实际数据库查询由六次变八次（标准词 100 复用 1000 聚合），查询间隔由五次变七次。
