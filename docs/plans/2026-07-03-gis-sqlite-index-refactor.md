# GIS 索引 SQLite 化重构实施方案

> For Hermes: Use subagent-driven-development skill to implement this plan task-by-task.

目标：在不改变现有 `/api/gis/*` 路由行为与返回逻辑的前提下，把 GIS 运行时索引从 `areacity.index.json` 全量加载改为 SQLite 持久化索引按需查询，降低启动/常驻内存占用。

架构：保留现有 `features.jsonl` 与 `subgeom.bin` 的职责，替换 `areacity.index.json` 为 `areacity.index.sqlite`。运行时 `ENGINE` 不再把 `grid_index` / `feature_parts` 全量读入 Python，而是通过 SQLite 表（优先 RTree + 映射表）查询候选 `sub_id`，再按原逻辑从 `subgeom.bin` 读取 geometry 做精确判定。API 路由、返回结构、geometry 精确判定逻辑保持不变。

技术栈：Python 3、sqlite3（标准库）、现有 FastAPI、现有 GeoJSON/JSON bin 存储。

---

## 现状与约束

1. 必须保持不变
- `/api/gis/status`
- `/api/gis/query/point`
- `/api/gis/query/point-with-tolerance`
- `/api/gis/query/geometry`
- `/api/gis/boundary/by-id`
- `/api/gis/search`
- `/api/gis/children`
- 现有 `QueryResult` / `EngineStatus` / `FeatureRecord` 对外结构
- 几何精确判定逻辑：`point_in_geometry` / `geometry_intersects_geometry` / `point_to_geometry_distance_metres`

2. 当前主要问题
- `scripts/geo/build_lowmem_index.py` 产出 `areacity.index.json`
- 运行时 `load_index()` 直接 `json.loads(path.read_text(...))`
- `grid_index` 被全量载入为 `dict[str, list[int]]`
- 当前实测：`grid_index` key 数量约 1458 万，`total_grid_refs` 约 5991 万
- 这导致 GIS 引擎第一次初始化时出现巨量 Python 对象常驻内存

3. 本次重构边界
- 不改变 GIS API 的业务语义
- 不做坐标系/几何算法重写
- 不引入外部数据库服务
- 不改为 PostGIS / SpatiaLite
- 优先使用 Python 标准库 sqlite3 完成

---

## 目标产物

新增/替换后的 GIS 索引资产：

- 保留：`data/geo/generated/engine/wgs84/areacity.features.jsonl`
- 保留：`data/geo/generated/engine/wgs84/areacity.subgeom.bin`
- 新增：`data/geo/generated/engine/wgs84/areacity.index.sqlite`
- 更新：`data/geo/generated/engine/wgs84/areacity.meta.json`
- 更新：`data/geo/generated/engine/wgs84/areacity.build_manifest.json`

废弃运行时主依赖：
- `data/geo/generated/engine/wgs84/areacity.index.json`

说明：如需兼容旧资产，可短期保留 json 文件生成逻辑，但运行时不得再依赖它。

---

## SQLite 索引设计

### 表 1：subgeometries
用途：替代原 `subgeometries` 列表。

字段建议：
- `sub_id INTEGER PRIMARY KEY`
- `feature_id INTEGER NOT NULL`
- `deep INTEGER NOT NULL`
- `part_index INTEGER NOT NULL`
- `part_kind TEXT NOT NULL`
- `source_geometry_type TEXT NOT NULL`
- `min_lng REAL NOT NULL`
- `min_lat REAL NOT NULL`
- `max_lng REAL NOT NULL`
- `max_lat REAL NOT NULL`
- `geom_offset INTEGER NOT NULL`
- `geom_length INTEGER NOT NULL`

说明：
- 这张表完全覆盖原 `SubGeometryIndexRecord` 运行时需要的数据
- `bbox` 在运行时可以从四个字段恢复为 tuple

### 表 2：subgeometry_rtree
用途：按 bbox 做候选召回，替代海量 `grid_index`。

建议：
- `CREATE VIRTUAL TABLE subgeometry_rtree USING rtree(sub_id, min_lng, max_lng, min_lat, max_lat)`

查询方式：
- 点查：`min_lng <= lng <= max_lng AND min_lat <= lat <= max_lat`
- bbox 查：`max_lng >= query_min_lng AND min_lng <= query_max_lng AND max_lat >= query_min_lat AND min_lat <= query_max_lat`

说明：
- 这一步是本次内存下降的核心
- 用 SQLite 的磁盘索引页替代 Python 内存 `grid_index`

### 表 3：feature_parts
用途：替代原 `feature_parts` 映射，用于 `/gis/boundary/by-id` 重建 geometry。

字段建议：
- `feature_id INTEGER NOT NULL`
- `sub_id INTEGER NOT NULL`
- `PRIMARY KEY (feature_id, sub_id)`

索引建议：
- `CREATE INDEX idx_feature_parts_feature_id ON feature_parts(feature_id)`

### 可选表 4：metadata / manifests
用途：若希望把 manifest 的关键字段也存入 sqlite，可加 key-value 表；但本次不必强制。

建议本次仍保留：
- `areacity.meta.json`
- `areacity.build_manifest.json`

---

## 代码改造方案

### 任务 1：配置层支持 sqlite 索引路径

目标：为新的 sqlite 索引文件增加标准配置入口，不影响现有其他路径。

修改文件：
- `app/geo_query/config.py`

要做：
- 新增 `GEO_INDEX_SQLITE_PATH = GEO_ENGINE_WGS84_DIR / "areacity.index.sqlite"`
- 保留 `GEO_INDEX_JSON_PATH` 仅作为兼容/迁移期常量（如仍需生成旧文件）
- 后续运行时 `engine`/`loader` 改为优先使用 sqlite

验证：
- `python3 -m py_compile app/geo_query/config.py`

### 任务 2：新增 sqlite 索引构建器逻辑

目标：让 `scripts/geo/build_lowmem_index.py` 产出 sqlite 索引，而不是仅产出 json 索引。

修改文件：
- `scripts/geo/build_lowmem_index.py`

要做：
- 新增 sqlite 初始化逻辑
- 创建 `subgeometries` / `subgeometry_rtree` / `feature_parts`
- 遍历 feature parts 时同步写入 sqlite
- 保留 `features.jsonl` / `subgeom.bin` 产出逻辑不变
- manifest 中新增：
  - `index_storage = "sqlite"`
  - `index_db_path`
  - 可能保留 `storage_format = "geojson-bytes"` 表示 geometry 存储方式
- 不再把 `grid_index` / `subgrid_index` 作为运行时必需资产输出

重点：
- `grid_cells_for_bbox()` 可删除或仅保留兼容模式；运行时主索引切换为 RTree
- `subgrid_refs` 可从运行时模型中退役，但若保守起见也可在 dataclass 中暂留为空

验证：
- 运行 `python3 scripts/geo/build_lowmem_index.py`
- 确认生成 `areacity.index.sqlite`
- 用 sqlite 查询表数量/样例行

### 任务 3：新增 sqlite index store

目标：运行时通过 sqlite 查询索引，不再 `json.loads` 整包 index。

修改文件：
- `app/geo_query/index_store.py`

建议重构方式：
- 保留 `load_features(path)`
- 替换/新增：
  - `connect_index_db(path)`
  - `load_subgeometry_by_ids(conn, sub_ids)`
  - `query_candidate_records_by_bbox(conn, bbox)`
  - `query_feature_part_ids(conn, feature_id)`
  - `count_subgeometries(conn)`

设计要求：
- 返回值要能无缝喂给现有 `SubGeometryIndexRecord`
- 不要在这里一次性把整库内容读出到 Python

验证：
- 针对小范围 bbox 查询，确认只返回候选 subgeometry
- `python3 -m py_compile app/geo_query/index_store.py`

### 任务 4：重构 engine 运行时加载方式

目标：`AreaCityQueryPy` 不再持有整包 `grid_index` / `feature_parts` 常驻内存，只保留 sqlite 连接和少量缓存。

修改文件：
- `app/geo_query/engine.py`
- `app/geo_query/models.py`（仅在确有必要时最小改动）

要做：
- `init_store_in_wkb_file()` 改为：
  - 读 `features.jsonl`
  - 打开 sqlite index db
  - 建立 geometry store
  - 读 meta
  - 不再 `load_index(index.json)`
- 删除/退役这些运行时大对象：
  - `self.grid_index`
  - `self.subgrid_index`
  - `self.feature_parts`（可改为按需查）
- 新增运行时持有：
  - `self.index_conn` 或线程安全的连接工厂
- `grid_candidates_for_bbox()` 改为调用 sqlite/RTree 查询
- `read_boundary_by_id()` / `rebuild_feature_geometry()` 改为按需查 `feature_parts`
- `get_status()` 中的 `index_path` 改为 sqlite 路径；兼容命名可保留但值应指向 sqlite 文件
- `feature_count` / `subgeometry_count` 仍保持语义不变

线程注意事项：
- sqlite3 默认连接线程限制需要明确处理
- 如果 FastAPI 请求在不同线程里跑，优先方案：
  - 引擎持有 db path，不共享单连接
  - 每次查询短连接访问 sqlite
- 若性能需要，可再讨论只读连接策略；本次以正确性优先

验证：
- `python3 -m py_compile app/geo_query/engine.py app/geo_query/index_store.py`
- 启动 GIS app 后访问 `/api/gis/status`
- 确认返回 loaded=true、feature_count/subgeometry_count 正常

### 任务 5：保持 query 逻辑完全不变

目标：point / geometry / tolerance 的业务判断保持原样，仅替换候选召回来源。

修改文件：
- `app/geo_query/query_ops.py`

要求：
- `filter_candidates()` 继续接收 `engine` + `query_bbox`
- 其内部来源从 `engine.grid_candidates_for_bbox()` 获得候选
- 后续 `bbox_intersects` / `point_in_geometry` / `geometry_intersects_geometry` 保持不变
- `stats` 字段逻辑保持尽量一致：
  - `envelope_hit_count` 仍表示 bbox 候选数量
  - `exact_hit_count` / `nearest_hit_count` / `io_reads` 保持原语义

验证：
- 对同一测试点与测试面，改造前后返回结果一致

### 任务 6：补 GIS 回归测试

目标：证明“逻辑不变”，而不仅是“能运行”。

新增文件建议：
- `tests/test_gis_routes_sqlite_index.py`
- `tests/test_geo_query_engine_sqlite.py`

至少覆盖：
1. `create_gis_app()` 启用 GIS 路由
2. `/api/gis/status` 可返回 loaded 状态
3. `/api/gis/query/point` 对北京测试点返回多层行政区
4. `/api/gis/query/point-with-tolerance` 行为不报错且返回结构正确
5. `/api/gis/search?q=北京` 返回北京相关项
6. `/api/gis/children?deep=0` 返回省级项
7. `/api/gis/boundary/by-id?feature_id=110101` 返回 geometry
8. engine 层 bbox 查询能拿到候选 subgeometry

如果测试环境不适合起完整服务，可组合：
- route 层 `TestClient`
- engine 层直接调用

验证命令建议：
- `. .venv/bin/activate && python -m pytest tests/test_gis_routes_sqlite_index.py -q`
- `. .venv/bin/activate && python -m pytest tests/test_geo_query_engine_sqlite.py -q`

### 任务 7：补等价性验证脚本/测试

目标：证明改造前后核心查询结果一致。

建议新增：
- `tests/test_geo_query_sqlite_equivalence.py`

内容：
- 选 3~5 个代表点位（如北京、广东、沿海附近）
- 选 1~2 个代表 geometry bbox / polygon
- 对旧 json 引擎和新 sqlite 引擎分别跑查询
- 断言：
  - `result` 中 feature id 集合一致
  - `boundary/by-id` 返回的 feature 元数据一致

如果不方便长期保留双实现：
- 可用临时基线文件或测试内直接读取旧 index.json 逻辑做对照
- 等价性测试通过后，再决定是否保留旧 loader 作为测试专用基线

---

## 风险与对策

### 风险 1：sqlite 线程使用问题
对策：
- 不共享跨线程连接
- 引擎保存 db path，每次查询建立只读短连接
- 后续如需优化，再做连接复用

### 风险 2：`boundary/by-id` 重建几何顺序变化
对策：
- `feature_parts` 查询需稳定排序，按 `sub_id` 或 `(part_index, sub_id)`
- 保持与原逻辑一致的去重键：`(source_geometry_type, part_index)`

### 风险 3：point/geometry 查询结果细微差异
对策：
- 候选召回由 RTree 替换 grid 后，理论上只要 bbox 条件正确，精确判定结果应不变
- 用等价性测试覆盖

### 风险 4：manifest / status 字段兼容
对策：
- 外部接口字段名不轻易改
- 必要时仅更新字段值，不改名字

### 风险 5：仓库当前脏工作树
对策：
- 提交时严格只 stage 本次 GIS 重构相关文件
- 提交前用 `git diff --cached --name-only` 确认范围

---

## 实施顺序

1. 配置常量新增 sqlite 路径
2. 构建脚本输出 sqlite 索引
3. index_store 新增 sqlite 查询接口
4. engine 切换到 sqlite 运行时
5. 验证 route 能跑通
6. 补 route / engine / 等价性测试
7. 跑测试与真实 curl 验证
8. 独立 CR
9. 修复 review 问题
10. scope-limited commit

---

## 完成标准

满足以下条件才能算完成：

1. `/api/gis/*` 路由全部可用
2. 现有业务逻辑与返回结构不变
3. 运行时不再 `json.loads` 整个 `areacity.index.json`
4. 运行时不再持有大 `grid_index` Python dict
5. GIS 索引主资产切换为 sqlite
6. 相关测试通过
7. 有真实 HTTP 验证结果
8. 已执行独立 CR 并修复阻塞问题
9. 已完成 scoped git commit
