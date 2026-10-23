# Toponyms 修复与验证记录

## 不可变约束

用户明确要求无限量返回。这覆盖了先前分析报告中“限制在线结果条数”的建议：

- points/search/普通 names 的 `limit=0` 完整返回所有匹配结果。
- 非零 limit 的既有 2,000,000 上限不变，没有强制分页、隐性行数上限或新增深页限制。
- 全量流没有两秒总时长上限；客户端断开时取消 SQL 并释放资源。
- 原来的名称树 full/lazy 机制保留。超过阈值的计数改为明确的下限，不伪造精确总数。

## 实现

1. 全量及 limit>5000 的响应改为标准 JSON 流，每次读取/编码 256 行。保留完整排序、字段、数量和截断语义；search 继续省略 null 字段。HTTP 客户端仍可使用 response.json()。
2. points 在无 bbox 的 contains/suffix 路径复用已有 type/name/id 覆盖索引筛选 ID，再取坐标；缺索引时回退原查询，不在运行时建索引。
3. search 不再无条件读取 area_code；名称树先探测至多 5001 个不同 name/area 对。少量命中直接复用结果构树。
4. 行政区只分批加载命中 code 与祖先；路径按 parent_code 逐层解析，支持跳级与 level 5。lazy 查询分批迭代区域，不加载整个 divisions 字典；details 去重后批量加载祖先。
5. 地名使用独立只读连接，4 MiB 页缓存目标、FILE 临时存储，请求结束关闭；不影响全站共享连接池。
6. 单机跨 worker 重查询最多 2 个，其中树最多 1 个；轻查询另有 1 个槽位。槽位由 POSIX flock 管理，不等待扩容、无自动重试。
7. 每 worker 仅缓存小响应：4 MiB 序列化数据、256 项、单项 128 KiB、30 秒 TTL，含数据库/WAL 版本键。全量流不进入结果缓存。小请求有界合并，最多 4 个 producer、8 个等待者。
8. 首批结果产生前与输出过程中均处理断连。独立审查发现 BaseHTTPMiddleware 会影响 is_disconnected 的取消式轮询，现改为等待 receive 的断连监视任务，并覆盖真实中间件回归。

资源边界以“同时运行多少工作、每批保留多少数据”实现，不以削减返回结果实现。SQLite 排序仍可能产生与数据量有关的临时磁盘 I/O；慢客户端占用查询槽位更久，满额返回 503 + Retry-After。途中错误会中断传输，不返回伪造的完整 JSON。

## 本地真实库测量

环境：macOS，Python 3.12 / SQLite 3.53.2；原始约 4.9 GB 数据库以只读连接访问。没有改表、建索引或连接生产服务器。

以下全部使用 `limit=0`。流式测试不断消费字节，不把大响应拼成 Python 对象；表格是单次本地观察值，操作系统缓存未清空，不是生产 p95/p99 或网络传输耗时。

| 操作 | 完整返回量 | 耗时 | 进程峰值 RSS |
|---|---:|---:|---:|
| points contains 黄村 | 990 个点 | 0.376 s | 35.1 MiB |
| search contains 黄村 | 990 条 | 0.179 s | 38.5 MiB |
| names contains 村 | 665,264 个不同名称 | 0.639 s | 38.6 MiB |
| points contains 村（独立进程） | 935,922 个点 | 4.975 s | 43.7 MiB |
| 名称树 contains 黄村（独立进程） | full 树 | 0.217 s | 27.2 MiB |
| 名称树 contains 村（同一树测试进程） | lazy_fallback，31 个根 | 0.453 s | 34.4 MiB |

“黄村”的完整 990 条点位与原 SQL 的数据、顺序逐项相等。全量“村”点位生成 82,389,909 字节，首批约 0.533 秒，最大单批输出 22,610 字节，进程基线约 28.9 MiB。作为对照，之前仅执行旧版全行政区加载函数就使本地独立进程峰值达到约 519.5 MiB；这不是生产端到端内存对比。

可复现全量消费的核心调用：

```python
from app.service.toponyms.streaming import QueryStream

stream = QueryStream("/absolute/path/toponyms.db", "points",
                    {"query": "村", "match_mode": "contains", "limit": 0})
try:
    chunk = stream.start()
    while chunk is not None:
        # 将 chunk 写给消费者；不要拼接完整结果后再测内存。
        if stream.done:
            break
        chunk = stream.read()
    print(stream.count)
finally:
    stream.close()
```

## 回归覆盖与限制

验证命令：

```bash
python -m pytest tests/test_toponyms_routes.py tests/test_toponyms_resources.py tests/test_toponyms_index_script.py tests/test_sql_routes_thread_offload.py -q
```

结果：**46 passed**，64 条既有依赖弃用警告。没有把额外检查中已确认的基线失败计入通过数。

- 12,001 条数据的 points/search/names 全量结果，不因旧建议的 200/500/5000 上限丢失任何行。
- 以原始 SQL 为基准比对 exact/prefix/suffix/contains、零结果、通配符、单/多类型、有/无 bbox 的全量数据及排序。
- 真实 RequestLogMiddleware + GZip + HTTP middleware 下完整输出 6001 条点位。
- 初始长 SQL 的断连、输出期间断连、共享请求单个等待者取消、跨进程并发槽、错误后连接/槽位可用性。
- 只读连接、有限请求 SQL 超时、小缓存内存预算/失效、不缓存失败、树路径与下限计数。
- 未进行生产压测或 2 核 / 2 GB 容器限制下的吞吐量验收，不据本地测量承诺生产指标。

额外检查发现：`tests/test_sql_tree_full_precheck.py` 在原始主工作区代码上同样失败（预期 lazy_fallback，实际 full），未改动其通用 SQL 实现。隔离工作区运行 `tests/test_sql_mapping.py` 时缺少未纳入 Git 的 gis.db；这是测试数据缺失，不是地名查询回归。

## 接口与部署注意事项

唯一结果元数据调整：树的 lazy_fallback 中 `filtered_count=null`，
`count_exact=false`、`count_lower_bound=5001`。前端应显示“至少 5001”，不能把 null 当 0。普通全量响应的结果集合和结构不变。

所有 worker 必须共用数据库路径和锁目录；不得在服务运行时删除锁文件。完整接口文档见 `docs/api/toponyms.md`。没有增加 worker、常驻服务或数据库索引，没有推送或部署。
