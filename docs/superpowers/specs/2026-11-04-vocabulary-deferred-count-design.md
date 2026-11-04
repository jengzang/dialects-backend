# 已批准的 Vocabulary 延后计数设计

用户已同意先返回页面、同 worker 响应后计算总数并复用现有缓存；前端最小化兼容。本地实施及测量，不部署、不修改生产。保留当前两个仓库无关修改。

entries 新增 defer_total=true 显式选择，缺省继续精确 total。新模式 LIMIT page_size+1，返回最多 page_size 条及 has_more；total 可为空。首页不满（包括恰好 page_size）或后续非空末页可以推出精确总数，空越界页不猜 total。缓存命中 total 仍直接复用，完整未知总数响应不缓存，完整已知响应仍复用现有有界缓存。原 entries-count SQL/values 键及版本失效不变。

Starlette BackgroundTasks 在响应发送后执行，同 worker、独立 Session，复用现有线程调度及 expensive=1/heavy=2 工作槽。跨 worker 全局后台计数 lease 最多一个；同条件复用现有 compute 锁，均不等待、无任务队列。无空位/锁忙则跳过，下次未知总数请求可重试。查询期限 5 秒，SQLite progress handler 真正中断查询；失败全局冷却 15 秒，不自动重试。Redis 不可用则不启动无法复用的计数。lease 120 秒覆盖期限，worker 丢失后自动过期。数据版本开始前核对、完成缓存写入原 Lua 原子核对。后台失败不改变已返回数据。持有跨 worker lease 后至多一项计数，临时 key 数为常数；不引入缓存总量扩张或新服务。

前端仅卡片列表及地图详情增加 has_more，显式发送 defer_total，旧后端没有 has_more 时兼容原 total 判断；保留 null 而非伪造总数。无轮询、新组件、样式或其他模式改动。

验证覆盖旧 API、各种搜索模式/简繁/孤立记录、0/恰好一页/多页/末页/越界、已有 count cache、推导计数、pending 不缓存、响应早于后台、独立连接、跨请求锁、资源忙、失败冷却、超时、版本变化和缓存故障。使用只读生产副本测量首包关键路径、后台额外工作和对照回归，明确不保证线上 OOM 或稀少查询改善。
