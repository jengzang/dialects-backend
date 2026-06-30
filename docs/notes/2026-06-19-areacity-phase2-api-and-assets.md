# AreaCity 第二阶段接口与资产说明

更新时间：2026-06-19

## 1. 目标

本阶段的目标不是再次做原始边界数据转换，而是在第一阶段已经产出的 WGS84 GeoJSON 基础上，生成适合 Python FastAPI 在线查询的运行时索引资产，并提供纯 Python 查询服务。

整体链路如下：

1. 上游仓库 AreaCity-JsSpider-StatsGov 提供行政区划边界数据。
2. 第一阶段脚本把数据转换为本项目可控的 WGS84 GeoJSON 标准中间产物。
3. 第二阶段脚本再把 GeoJSON 构建为运行时索引资产。
4. FastAPI 在启动时加载查询引擎，对外提供点查、容差点查、几何查询、边界读取等接口。

## 2. 目录结构

### 原始与中间数据
- `data/geo/source/`
  - 原始来源数据
- `data/geo/generated/geojson/wgs84/`
  - 第一阶段标准中间产物

### 第二阶段运行时资产
- `data/geo/generated/engine/wgs84/areacity.index.json`
  - 子几何索引主文件
  - 当前包含 `subgeometries`、`grid_index`、`feature_parts`
- `data/geo/generated/engine/wgs84/areacity.features.jsonl`
  - 每行一个 feature 属性记录
- `data/geo/generated/engine/wgs84/areacity.subgeom.bin`
  - 几何二进制池
  - 当前存储格式为 `geojson-bytes`，不是 WKB
- `data/geo/generated/engine/wgs84/areacity.meta.json`
  - 运行时元信息
- `data/geo/generated/engine/wgs84/areacity.build_manifest.json`
  - 构建清单

### 脚本与服务
- `scripts/geo/build_lowmem_index.py`
  - 第二阶段离线构建脚本
- `scripts/geo/verify_fastapi_geo.py`
  - 第二阶段接口验证脚本
- `app/geo_query/`
  - 纯 Python 查询引擎
- `app/routes/geo/areacity_query.py`
  - FastAPI 路由层

## 3. 第二阶段资产格式说明

### 3.1 areacity.features.jsonl
每行一个行政区 feature 的属性对象，不含 geometry 本体。当前字段包括：
- `id`
- `pid`
- `deep`
- `name`
- `ext_path`
- `center_lng`
- `center_lat`
- `source_crs`
- `target_crs`
- `source_file`
- `geometry_type`
- `geometry_exists`

作用：
- 让查询时能快速返回属性，不必每次读整个 GeoJSON。

### 3.2 areacity.subgeom.bin
这是几何池文件。
当前实现中，每个几何以紧凑 JSON 字节串形式顺序写入，并通过：
- `geom_offset`
- `geom_length`
进行定位读取。

注意：
- 文件名是 `.bin`
- 元信息中的 `storage_format` 为 `geojson-bytes`
- 当前不是 WKB

作用：
- 避免把所有 geometry 放回一个大 JSON 文件里运行时反复解析
- 支持按偏移懒加载

### 3.3 areacity.index.json
当前包含三部分：

1. `subgeometries`
   - 每条记录包括：
     - `sub_id`
     - `feature_id`
     - `deep`
     - `bbox`
     - `geom_offset`
     - `geom_length`

2. `grid_index`
   - 网格倒排索引
   - key 形如 `x:y`
   - value 为命中的 `sub_id` 数组

3. `feature_parts`
   - `feature_id -> [sub_id, ...]`
   - 供按 id 读边界时快速定位其子几何

### 3.4 areacity.meta.json / areacity.build_manifest.json
当前主要字段：
- `source`
- `grid_factor`
- `storage_format`
- `source_crs`
- `target_crs`
- `feature_count`
- `subgeometry_count`
- `generated_at`

## 4. 当前查询引擎设计

### 4.1 核心模块
- `config.py`
  - 管理路径与配置常量
- `models.py`
  - 定义 feature / index / status / query result 数据结构
- `index_store.py`
  - 加载 json/jsonl 索引资产
- `geometry_store.py`
  - 按 offset/length 读取几何池
- `geometry_utils.py`
  - bbox、点在面内、线段相交、几何相交、距离计算等纯 Python 几何工具
- `query_ops.py`
  - 实现点查、容差点查、几何查询
- `engine.py`
  - 引擎主入口
- `loader.py`
  - 全局单例加载与并发初始化保护

### 4.2 当前查询流程

#### 点查 `/gis/query/point`
1. 将点转成点 bbox
2. 通过 `grid_index` 找候选 subgeometry
3. 再做 bbox 过滤
4. 懒加载 geometry
5. 用纯 Python 点在面内算法判断命中

#### 容差点查 `/gis/query/point-with-tolerance`
1. 先做普通点查
2. 如无命中，则根据 `tolerance_metre` 构造 buffer bbox
3. 用 `grid_index` 缩小候选范围
4. 计算点到 polygon 边界的最短距离
5. 每个 deep 返回最近命中项

#### 几何查询 `/gis/query/geometry`
1. 计算输入几何 bbox
2. 通过 `grid_index` + bbox 找候选
3. 懒加载 geometry
4. 用纯 Python 几何相交逻辑判断：
   - 顶点落入对方 polygon
   - 线段相交

#### 按 id 取边界 `/gis/boundary/by-id`
1. 用 `feature_parts` 找到该 feature 对应的 sub_id 列表
2. 读取 geometry
3. 返回统一结构：
   - `{"feature": ..., "geometry": ...}`
4. 如果存在多个子几何，当前会用 `GeometryCollection` 包起来返回

## 5. FastAPI 接口说明

统一前缀：`/api`

### 5.1 状态接口
GET `/api/gis/status`

返回示例字段：
- `loaded`
- `mode`
- `feature_count`
- `subgeometry_count`
- `source_crs`
- `target_crs`
- `storage_format`
- `grid_factor`
- `index_path`
- `features_path`
- `geometry_path`

### 5.2 名称搜索
GET `/api/gis/search?q=北京&deep=0`

参数：
- `q`: 必填，最小长度 1
- `deep`: 可选，0~2

### 5.3 children 查询
GET `/api/gis/children?parent_id=11&deep=1`

参数：
- `parent_id`: 可选，>=0
- `deep`: 可选，0~2

### 5.4 边界读取
GET `/api/gis/boundary/by-id?feature_id=11`

参数：
- `feature_id`: 必填，>=1

### 5.5 点查
GET `/api/gis/query/point?lng=116.397128&lat=39.916527`

参数：
- `lng`: -180~180
- `lat`: -90~90

### 5.6 带容差点查
GET `/api/gis/query/point-with-tolerance?lng=121.993491&lat=29.524288&tolerance_metre=2500`

参数：
- `lng`: -180~180
- `lat`: -90~90
- `tolerance_metre`: >=0

### 5.7 几何查询
POST `/api/gis/query/geometry`

Body:
```json
{
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[116.3, 39.8], [116.5, 39.8], [116.5, 40.0], [116.3, 40.0], [116.3, 39.8]]]
  }
}
```

限制：
- 当前仅支持 `Polygon` / `MultiPolygon`
- 必须带 `coordinates`

## 6. 已完成的验证

### 6.1 资产构建
执行：
- `python3 scripts/geo/build_lowmem_index.py`

最新验证结果：
- `feature_count = 3635`
- `subgeometry_count = 3257`
- `source_crs = WGS84`
- `target_crs = WGS84`
- `storage_format = geojson-bytes`

### 6.2 语法检查
执行：
- `python3 -m py_compile ...`

结果：通过

### 6.3 接口验证
执行：
- `.venv/bin/python scripts/geo/verify_fastapi_geo.py`

已验证：
- `/api/gis/status` -> 200
- `/api/gis/search?q=北京` -> 200
- `/api/gis/children?deep=0` -> 200
- `/api/gis/boundary/by-id?feature_id=11` -> 200
- `/api/gis/query/point` -> 200
- `/api/gis/query/point-with-tolerance` -> 200
- `/api/gis/query/geometry` -> 200
- 非法 `lng=999` -> 422
- 非法 geometry type `Point` -> 422

## 7. 当前实现的边界与后续优化方向

当前实现已经满足：
- 纯 Python
- FastAPI
- 离线准备脚本与在线服务分层
- 运行时索引资产独立于 app/
- 具备可运行的第二阶段查询能力

但它仍然是“Python 可运行版第二阶段”，不是最终极限优化版。后续优化建议如下：

### 7.1 真正的 subgeometry 拆分
当前每个 feature 基本仍对应一个 subgeometry 记录。
后续可以把大 polygon 按 ring/块进一步切分，以减少大面查询成本。

### 7.2 更细粒度网格/层级索引
当前 `grid_factor=100`，属于较粗的网格。
后续可根据命中分布和资产体积调优，甚至按 deep 分层索引。

### 7.3 GeometryCollection 返回策略
当前多子几何返回 `GeometryCollection` 以保持外层结构统一。
后续如果前端或调用方明确要求，也可以改为：
- 尝试重组为 `MultiPolygon`
- 或显式返回标准化的 boundary payload schema

### 7.4 几何缓存策略
当前 `_geometry_cache` 是进程内缓存。
后续可考虑：
- LRU
- 大小上限
- 命中统计
- 冷热分层

### 7.5 可选高性能几何加速
如果后续要支持更高吞吐或更复杂几何，可以考虑提供可选加速层：
- shapely
- rtree / 更强空间索引

但这应作为可选增强，不影响当前纯 Python 基线实现。

## 8. 推荐使用方式

### 重建第二阶段资产
```bash
python3 scripts/geo/build_lowmem_index.py
```

### 验证接口
```bash
.venv/bin/python scripts/geo/verify_fastapi_geo.py
```

### 启动服务后使用接口
直接访问：
- `/api/gis/status`
- `/api/gis/search`
- `/api/gis/query/point`
- `/api/gis/query/point-with-tolerance`
- `/api/gis/query/geometry`
- `/api/gis/boundary/by-id`

## 9. 总结

第二阶段的正确定位是：
- 输入：第一阶段 WGS84 GeoJSON
- 输出：运行时索引资产 + Python 查询引擎 + FastAPI 接口

与官方 Java 示例的关系是：
- 借鉴查询引擎思想
- 不直接照抄 Java Web 层
- 结合本项目现有 FastAPI 架构落地
