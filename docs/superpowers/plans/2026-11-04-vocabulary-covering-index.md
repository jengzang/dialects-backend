# Vocabulary 地图优先与覆盖索引实施计划

用户已确认设计和执行顺序：先前端，再后端，最后生产建索引。沿用当前 dev 工作区，保留其他未提交修改；不部署应用、不重启、不修改服务器配置。

- [x] 前端：在现有 vocabularySearchEntrance / vocabularyQueryControls 测试中增加真实挂载的延迟 Promise 场景；验证地图先请求、标准词独立 loading、空地图可展示、标准词失败不清除选择、过期查询不继续加载旧选项。修改现有两个 Vue 文件，不拆组件；运行相关测试和本地 Vite build，审查 diff 后单独提交。
- [x] 后端：增加 tests/test_vocabulary_search_cover.py；有正确完整索引时，仅无范围的默认内容字段普通字面量聚合使用覆盖索引。无索引、索引定义错误、通配符、其他字段、范围查询保留原路径。按索引 schema 检查有限元数据，不缓存候选 ID，不启动任务，不在启动自动建新索引。验证全部响应等价、计划、写入后结果和同名地点隔离；运行 vocabulary 回归；审查并提交。
- [ ] 生产：先只读检查资源、数据库写入任务、索引与 journal 状态。使用独立 Python sqlite 连接，不加载应用；单进程、nice19、ionice idle、小页缓存、temp_store=FILE、禁用自动 checkpoint、短 busy timeout 和硬截止。DDL 在 WAL 下允许读但占写锁，不能承诺零影响；有导入/写入或资源不满足时不开始。建索引仅一次，不自动重试，不 ANALYZE/VACUUM/改持久配置。进程内监控可用内存；宿主看护监控可用内存、swap、新完成的写请求，5 秒发送 INT，1 秒后仍运行则 KILL。没有可靠的待处理写者或在线延迟指标，不声称能监控它们；以 100ms 锁等待和短迁移截止限制写影响，异常后只读核对提交状态。
- [ ] 完成：验证索引名称/字段/非 partial/非 unique/正常排序；使用 EXPLAIN 验证覆盖计划，不在生产重放聚合。记录实际耗时、文件增长、内存峰值和前后资源。单独报告现有生产应用 NOT INDEXED 尚需用户正常发布本地代码才能受益。

生产首次 4 秒执行预算触发，已核对索引不存在、DB/WAL 大小未变，服务运行且最近 10 分钟无内核 OOM 记录；可用内存最低 327 MiB、swap 未增加。基于该测量，允许一次人工调整为 8 秒的尝试；仍单核、nice19、idle I/O、1 MiB cache、96 MiB 虚拟内存上限、100ms 争锁等待和 128 MiB 可用内存退出线。看护在预算+1秒发 INT，1秒后仍在则发 KILL，并通过 nonce/NSpid/starttime 直接确认宿主目标，不依赖 Docker 信号转发。没有循环重试。

8 秒 idle-I/O 尝试同样超时并回滚，采样 CPU 0.85 秒、RSS 17484 KiB，可用内存最低 306.9 MiB。只读检查容器限制 1.5 CPU / 1.5 GiB，内存使用约 1136 MiB、failcnt=0；即时宿主 CPU 大部分空闲、磁盘约7ms/s忙碌。最后一次策略验证保持8秒窗口，改用 best-effort 最低I/O优先级7，保留 nice19，SQLite threads=0但不强制固定CPU0。新增容器可用余量128MiB启动/64MiB退出保护。不得再无限扩大预算或循环在线重试。
