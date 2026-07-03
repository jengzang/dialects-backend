# GIS sqlite 化后真实 API 验证补充记录

时间：2026-07-03

目标：
1. 真实命中 `point-with-tolerance` 的 nearest fallback 分支
2. 记录 sqlite 化后的运行时内存 / 请求证据

## 实际服务

启动命令：

`. .venv/bin/activate && python -m uvicorn app.entrypoints.gis_app:app --host 127.0.0.1 --port 8094`

## 实际 API 请求记录

### 1. `/api/gis/query/point-with-tolerance` nearest fallback 命中

请求：

`GET /api/gis/query/point-with-tolerance?lng=114.6&lat=22.2&tolerance_metre=30000`

结果特征：
- `exact_hit_count = 0`
- `nearest_hit_count = 3`
- 返回：
  - 广东省
  - 惠州市
  - 惠阳区
- 且每条结果带有：
  - `point_distance`
  - `point_distance_id`

这证明：
- 该请求没有直接落在 polygon 内
- 已实际进入 nearest fallback 分支
- fallback 分支返回结构正确

### 2. 其他真实请求样例

- 北京点查：`/api/gis/query/point?lng=116.4074&lat=39.9042`
  - 命中：北京市 / 北京市 / 东城区
- 广州点查：`/api/gis/query/point?lng=113.2644&lat=23.1291`
  - 命中：广东省 / 广州市 / 越秀区
- 上海容差点查：`/api/gis/query/point-with-tolerance?lng=121.4737&lat=31.2304&tolerance_metre=3000`
  - 命中：上海市 / 上海市 / 黄浦区
- 搜索：`/api/gis/search?q=广东`
  - 返回广东省及其下属大量行政区项
- children：`/api/gis/children?parent_id=44`
  - 返回广东省下属地级市列表
- boundary：`/api/gis/boundary/by-id?feature_id=440103`
  - 返回荔湾区真实 Polygon geometry
- geometry 查询：
  - 广州矩形框 polygon 请求实际命中广州多个区及佛山南海区

## sqlite 运行时证据

### 1. status 接口

`/api/gis/status` 返回：
- `mode = lowmem-sqlite`
- `index_path = .../areacity.index.sqlite`
- `subgeometry_count = 10457`

### 2. sqlite 资产一致性

实查：
- `meta_subgeometry_count = 10457`
- `subgeometries = 10457`
- `subgeometry_rtree = 10457`
- `feature_parts = 10457`
- `index_storage = sqlite`

说明：
- manifest / meta 与 sqlite 库内部行数一致
- 当前运行时主索引资产确实是 sqlite

## 运行时内存证据

实测命令（真实运行中的 uvicorn 进程）：
- `ps -o pid,rss,vsz,command -p <bash_pid>,<python_pid>`

一次真实观测到的 uvicorn Python 进程 RSS：
- `PID 91135 RSS 331808 KB`
- 约 `324 MB`

补充说明：
- 这是一次真实服务启动并完成多次请求后的现场观测值，不是受控基准测试。
- 该值包含：
  - Python / FastAPI 进程本身
  - features 元数据
  - geometry LRU cache 热数据
  - 其他 app 级依赖
- 它只能证明 sqlite 化后的真实运行量级；不能单独当作严格的前后对照基准。
- 但可以确认：当前运行时已不再依赖把超大 `grid_index` JSON 全量反序列化进 Python 内存。

## 结论

1. `point-with-tolerance` 的 nearest fallback 分支已被真实请求命中并验证通过
2. sqlite 化后的 GIS 运行时链路真实可用
3. 当前 `/api/gis/*` 多个真实请求均正常
4. sqlite 文件、manifest 与运行时 status 互相印证，说明运行时主索引已切换为 sqlite
