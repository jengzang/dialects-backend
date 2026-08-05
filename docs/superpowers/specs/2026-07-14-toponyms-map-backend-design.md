# 自然村地名地图后端设计方案

## 目标

实现自然村地名地图的后端能力，让前端可以在地图上展示自然村点位、按需获取地名文本、点击点位后用地名 `id` 直接请求民政部详情服务。

本方案以 `docs/plan/自然村地名地图查询系统_PRD.md` 和 `docs/plan/自然村地名地图系统_后端Agent开发文档.md` 为输入，但不完全采纳其中接口示例。原文档建议在同一个 GeoJSON feature 中返回 `id/name/longitude/latitude`，这违反当前硬性约束，必须调整。

硬性契约：

- 任何公开 API 响应都不能同时返回经纬度和对应地名。
- 坐标类 API 只能返回 `id`、`longitude`、`latitude` 以及与渲染有关但不含地名的信息。
- 地名类 API 只能返回 `name` 文本，不返回 `id`、经纬度、行政区编码或其他可直接回连坐标的键。
- 不把 `toponyms.db` 加入通用 SQL 查询白名单，避免用户通过 `/sql` 自选列重组 `id/name/longitude/latitude`。

## 已探索事实

当前仓库已有 `data/toponyms.db`，不是文档中单表 `toponyms` 的形状。

数据库结构：

```text
divisions(code TEXT PRIMARY KEY, name TEXT, parent_code TEXT, level INTEGER,
          single_cnt INTEGER, multi_cnt INTEGER, longitude REAL, latitude REAL, ur_code TEXT)
single(id TEXT PRIMARY KEY, standard_name TEXT, place_type TEXT, place_type_code TEXT,
       area_code TEXT, longitude REAL, latitude REAL)
multi(id TEXT PRIMARY KEY, standard_name TEXT, place_type TEXT, place_type_code TEXT,
      area_code TEXT, coordinates BLOB)
place_type_mapping(place_type_code TEXT PRIMARY KEY, place_type TEXT,
                   level1_code TEXT, level1_name TEXT, level2_code TEXT,
                   level2_name TEXT, level3_code TEXT, level3_name TEXT,
                   single_cnt INTEGER, multi_cnt INTEGER)
```

数据规模：

```text
single: 9,359,099
multi: 2,106,635
divisions: 739,719
place_type_mapping: 147
toponyms.db: page_count 713,190, page_size 4,096, about 2.7GB
```

自然村最贴近类别：

```text
place_type_code=22200, place_type=农村居民点, single_cnt=4,343,313
multi count for 22200=0
```

坐标质量：

```text
single 共有 9,359,099 条，无 NULL 经纬度。
农村居民点 4,343,313 条，全部落在 longitude 73..136 且 latitude 3..54 范围内。
```

现有索引：

```text
single: PRIMARY KEY(id), idx_single_place_type(place_type)
multi: PRIMARY KEY(id), idx_multi_place_type(place_type)
divisions: PRIMARY KEY(code), idx_divisions_level(level), idx_divisions_parent(parent_code)
```

性能风险：

- `WHERE place_type_code='22200' AND area_code LIKE '44%'` 当前全表扫描。
- `WHERE place_type_code='22200' AND longitude BETWEEN ... AND latitude BETWEEN ...` 当前全表扫描。
- `place_type_code=22200 AND area_code LIKE '44%'` 约 232,614 条。
- 一个广东常见地图 bbox 示例约 48,705 条。
- 仅 `id + longitude + latitude` 原始字段平均长度约 53 字符，不含 JSON 结构。4,343,313 个点做一次性 JSON 响应会非常大，前端也难以一次性渲染。

现有后端事实：

- `app/main.py` 已启用 `GZipMiddleware(minimum_size=1024)`，普通 JSON 响应会自动 gzip。
- 通用 SQL 路由基于 `app/common/path.py::DB_MAPPING` 暴露数据库；`toponyms.db` 当前未加入，必须继续保持不加入。
- 路由注册集中在 `app/routes/__init__.py`。
- SQLite 连接池可复用 `app/sql/db_pool.py::get_db_pool`。

## 关键设计判断

### 不采用原文档的单接口 GeoJSON

原 PRD 的 `GET /api/toponyms/map` 返回 GeoJSON，`geometry.coordinates` 和 `properties.name` 位于同一个 feature。这个设计让用户一次请求即可拿到 `id/name/lng/lat` 的完整映射，和当前反爬约束正冲突。

本方案废弃这个响应形状。即使前端使用 MapLibre，也应由前端把坐标 API 的 `id/lng/lat` 转为 GeoJSON source，弹窗标题不能从同一响应获得。

### 不一次性返回 434 万自然村点

文档说第一版直接返回全部自然村，但真实数据规模显示这不适合上线：

- 后端未索引查询会慢。
- JSON 响应体很大。
- 浏览器解析和 MapLibre 渲染压力极高。
- 一次性全量下载也让爬取成本最低。

推荐第一版就做“分区或视窗加载”，不是复杂反爬，而是正常地图工程边界。

## 推荐接口

### 1. 坐标视窗接口

```http
GET /api/toponyms/points?bbox=minLng,minLat,maxLng,maxLat&zoom=8&limit=5000
```

返回：

```json
{
  "items": [
    {"id": "61bc78d908dc1a594df878efe23b10f9", "longitude": 113.261082, "latitude": 23.135}
  ],
  "count": 1,
  "truncated": false,
  "next": null
}
```

约束：

- 只查 `single` 表。
- 默认过滤 `place_type_code='22200'`。
- 不返回 `standard_name`、`place_type`、`area_code`、行政区名。
- `bbox` 必填，避免全库导出。
- `limit` 默认 5000，最大 20000。超过上限返回 `truncated=true`，前端应继续放大地图或切分 bbox。
- `zoom` 可选，用于后续低 zoom 聚合；第一版可只校验，不参与查询。

边界处理：

- `bbox` 必须是 4 个有限数字。
- `minLng < maxLng`、`minLat < maxLat`。
- 限制全球范围：经度 `-180..180`、纬度 `-90..90`。
- 拒绝面积过大的 bbox，例如经纬度面积超过 `25` 时返回 400，提示前端先用分区概览或继续缩放。
- 过滤异常坐标：`longitude BETWEEN -180 AND 180`、`latitude BETWEEN -90 AND 90`。
- 返回顺序用 `ORDER BY id` 保持稳定分页，不用随机顺序破坏缓存。

### 2. 行政区概览接口

```http
GET /api/toponyms/divisions?parent_code=44
```

返回：

```json
{
  "items": [
    {
      "code": "4401",
      "name": "广州市",
      "level": 2,
      "longitude": 113.264385,
      "latitude": 23.129112,
      "single_count": 12345
    }
  ]
}
```

这个接口会同时返回行政区名称和行政区中心坐标。它不是“自然村地名对应坐标”，但仍有一定映射信息。若想把硬约束解释到最严，应改成：

```json
{"code":"4401","level":2,"single_count":12345}
```

推荐采用较严版本：公开接口不返回行政区中心坐标，只返回树结构和计数。前端可以用本地底图或已知行政区边界定位，不用从此接口拿中心点。

### 3. 地名批量文本接口

```http
GET /api/toponyms/names/sample?q=黄&limit=20
```

返回：

```json
{
  "items": ["黄村", "黄泥村", "黄塘村"]
}
```

约束：

- 只返回名称字符串数组。
- 不返回 `id`、经纬度、`area_code`、排序键。
- 不提供按 `id` 查名称的 API。
- 不提供 `ids[]=...` 批量换名接口，因为这会让坐标接口返回的 `id` 被直接回连到地名。

这个接口只用于搜索建议。前端若需要点击点位展示官方详情，应把坐标接口里的 `id` 传给民政部接口；后端不代理、不补名称。

### 4. 可选名称词典接口

如果产品坚持前端本地搜索，可提供一个“仅地名词典”下载：

```http
GET /api/toponyms/names-dictionary?prefix=黄&limit=10000
```

返回：

```json
{"items":["黄村","黄泥村","黄塘村"]}
```

它不和坐标接口共享分页游标或顺序，不返回总数，不返回 id。前端只能用它做文本搜索建议，不能可靠拼回点位。

## 不推荐接口

以下接口不要实现：

```http
GET /api/toponyms/map
GET /api/toponyms/{id}
GET /api/toponyms/names?ids=...
GET /api/toponyms/search
```

原因：

- `/map` 这个名称容易让开发者沿用 PRD 的 GeoJSON 示例，把 name 和 coordinates 合并。
- `/{id}` 和 `names?ids=...` 会把坐标接口里的 ID 直接换成地名。
- `/search` 如果返回搜索结果的 `id` 或坐标，也会形成完整映射。若做搜索，只能返回纯名称列表。

## 数据访问层设计

新增模块：

```text
app/service/toponyms/config.py
app/service/toponyms/repository.py
app/routes/toponyms.py
app/schemas/toponyms.py
tests/test_toponyms_routes.py
```

职责：

- `config.py`: 定义 `TOPONYMS_DB_PATH`、自然村类别码、limit/bbox 阈值。
- `repository.py`: 只暴露专用查询函数，禁止通用列选择。
- `routes/toponyms.py`: 参数校验、线程池 offload、响应模型。
- `schemas/toponyms.py`: Pydantic 模型，确保响应字段固定。
- `tests/test_toponyms_routes.py`: 用临时 SQLite 构造最小库，验证不泄露字段。

连接方式：

- 使用 `get_db_pool(TOPONYMS_DB_PATH, pool_size=4)`。
- 路由中使用 `starlette.concurrency.run_in_threadpool` 或 `asyncio.to_thread` 执行 SQLite 查询，避免阻塞事件循环。

路径配置：

- 在 `app/common/path.py` 增加：

```python
TOPONYMS_DB_PATH = os.path.join(BASE_DIR, "data", "toponyms.db")
```

- 不加入 `DB_MAPPING`。

路由注册：

- 在 `app/routes/__init__.py::setup_main_routes` 注册 `toponyms_router`，prefix 为 `/api`，继续挂 `ApiLimiter`。
- 不注册到 `setup_gis_routes`，除非未来 GIS 子服务需要它。当前自然村地图属于主站功能。

## 索引策略

当前库缺少支持地图查询的索引。建议数据侧或迁移脚本先在副本验证，再应用到正式库。

推荐第一组索引：

```sql
CREATE INDEX IF NOT EXISTS idx_single_type_lng_lat_id
ON single(place_type_code, longitude, latitude, id);

CREATE INDEX IF NOT EXISTS idx_single_type_area_id
ON single(place_type_code, area_code, id);

CREATE INDEX IF NOT EXISTS idx_single_type_name
ON single(place_type_code, standard_name);
```

说明：

- bbox 查询使用 `(place_type_code, longitude, latitude, id)`，SQLite 可先按类型和经度范围缩小，再过滤纬度。
- 行政区筛选使用 `(place_type_code, area_code, id)`。
- 纯地名建议使用 `(place_type_code, standard_name)`。如果需要 `LIKE '%黄%'`，普通索引帮助有限，应改为前缀搜索或 FTS5；第一版建议只支持前缀/包含中的前缀模式。

如需要按行政区前缀查询省/市/县下所有点，不要长期依赖 `area_code LIKE '44%'`。更稳的做法：

- 用 `divisions` 递归找到目标行政区下属叶子 code；
- 查询 `single.area_code IN (...)`；
- 若 IN 列表过大，分批查询并合并。

SQLite 可选优化：

```sql
ANALYZE;
```

如果索引体积不可接受，第二阶段改为预计算地图瓦片或分片 JSON，而不是让在线 API 扫大表。

## 响应格式选择

坐标接口不直接返回 GeoJSON。原因：

- GeoJSON 的常见习惯是在 `properties` 中带 `name`，容易破坏契约。
- 简洁数组比 GeoJSON 更小。
- 前端可以安全地构造只含 `id` 的 GeoJSON：

```json
{
  "type": "Feature",
  "geometry": {"type": "Point", "coordinates": [113.1, 23.2]},
  "properties": {"id": "123"}
}
```

如果必须后端返回 GeoJSON，只允许：

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {"type": "Point", "coordinates": [113.1, 23.2]},
      "properties": {"id": "123"}
    }
  ]
}
```

严禁 `properties.name`。

## 缓存与压缩

已有 gzip 中间件可覆盖 JSON 响应。仍建议：

- 对 `GET /api/toponyms/points` 设置短缓存，例如 `Cache-Control: public, max-age=300`。
- 对行政区树设置长缓存，例如 `Cache-Control: public, max-age=86400`。
- 对纯地名建议设置短缓存，避免频繁扫 name 查询。
- 不缓存错误响应。

如果 bbox 查询成为热点，第二阶段加入服务端 tile cache：

```text
cache key = place_type_code + z/x/y 或 normalized bbox + limit
value = id/lng/lat array only
```

缓存值仍不能包含地名。

## 反爬边界

本方案不是强反爬，只是提高爬取完整映射的难度。它能防止“一次 API 直接得到 id/name/坐标映射”，但不能防止：

- 用户拿坐标 `id` 逐个请求民政部接口。
- 用户分别抓坐标接口和纯名称词典后尝试靠外部数据模糊匹配。
- 用户抓前端渲染状态。

因此必须坚持：

- 后端永远不提供 `id -> name` 能力。
- 后端永远不提供 `name -> id/coordinate` 能力。
- 日志和错误响应不要输出 SQL、行内容或字段样例。
- API 文档中明确写出“不支持按 ID 查询地名”。

## 测试计划

单元测试：

- 临时 SQLite 创建 `single/divisions/place_type_mapping`。
- `points` 响应只包含 `id/longitude/latitude`。
- `points` 响应不包含 `standard_name/name/place_type/area_code`。
- `names` 响应是字符串数组，不包含对象、id、坐标。
- bbox 缺失、格式错误、面积过大、limit 过大返回 400。
- 默认只返回 `place_type_code=22200`。
- 空结果返回 `items=[]`，不是 404。

集成测试：

- FastAPI TestClient 调 `/api/toponyms/points`。
- 确认 gzip 中间件对大响应生效。
- 确认 `toponyms` 不在 `/sql` 可选 `DB_MAPPING` 中。
- 确认 `/api/toponyms/{id}` 不存在。

性能验证：

- 在本地 `data/toponyms.db` 上跑：

```sql
EXPLAIN QUERY PLAN
SELECT id, longitude, latitude
FROM single
WHERE place_type_code = '22200'
  AND longitude BETWEEN ? AND ?
  AND latitude BETWEEN ? AND ?
ORDER BY id
LIMIT ?;
```

- 期望使用 `idx_single_type_lng_lat_id`，而不是 `SCAN single`。
- 用广东省级、广州市级、一个乡镇级 bbox 各测一次响应时间和响应体大小。

## 实施顺序

1. 增加 `TOPONYMS_DB_PATH`，但不加入 `DB_MAPPING`。
2. 写 schemas 和参数校验测试。
3. 写 repository，固定列查询。
4. 写 `GET /api/toponyms/points`，只返回坐标包。
5. 写 `GET /api/toponyms/names/sample`，只返回名称字符串。
6. 写行政区树接口，采用严格版不返回行政区中心坐标。
7. 注册路由和限流。
8. 添加索引迁移说明或一次性维护脚本。
9. 更新后端接口文档，明确废弃 PRD 中 `id/name/coordinates` 合并示例。

## Open Questions

1. 产品是否接受第一版不再“一次性加载全部自然村”，而改为 bbox/分区加载？从数据规模看这是强烈推荐。
2. 行政区概览是否允许返回行政区中心坐标？若按硬约束最严解释，不应返回。
3. 地名搜索是否必须支持包含搜索。如果必须支持，需要 FTS5 或预处理词典，但输出仍只能是纯名称列表。
4. 是否只展示 `place_type_code=22200` 农村居民点，还是也包括行政村 `21610`、村民委员会 `27610`？若产品说“自然村”，推荐只用 `22200`。

## 结论

后端可以实现这个需求，但应修正原需求文档的接口形状。推荐以专用 `toponyms` 路由读取 `data/toponyms.db`，坐标接口只给 `id/lng/lat`，地名接口只给 `name` 字符串，并通过 bbox/limit/行政区树控制数据量。不要把 `toponyms.db` 暴露给通用 SQL 功能，也不要提供任何 `id <-> name` 的后端转换接口。
