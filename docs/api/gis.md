# GIS API 前端接入文档

GIS API 提供行政区划检索、行政层级消歧、边界读取和空间查询能力。所有新 GIS 接口都挂在 `/api/gis/**` 下。

本文面向前端接入，重点说明每个接口该怎么用、分别负责什么、返回什么，以及哪些场景不要混用。

## 快速结论

前端最常用的链路是：

1. 用户输入地名时，用 `GET /api/gis/search?q=...` 做候选搜索或下拉提示。
2. 用户确定行政层级后，用 `GET /api/gis/resolve?...` 消歧，拿到稳定的 `feature.id`。
3. 需要地图边界时，用 `GET /api/gis/boundary/by-id?feature_id=...` 获取 GeoJSON。
4. 需要“某个坐标落在哪些行政区”时，用 `GET /api/gis/query/point`。
5. 需要“某个面与哪些行政区相交”时，用 `POST /api/gis/query/geometry`。

如果你要查“东莞市边界”，推荐这样做：

```http
GET /api/gis/resolve?province=广东省&city=东莞市
```

如果返回 `matched: true`，再用返回的 `feature.id`：

```http
GET /api/gis/boundary/by-id?feature_id=<上一步返回的 feature.id>
```

不要直接用 `search?q=东莞市` 的第一个结果当最终结果。`search` 是候选搜索，不负责消歧。

注意：能否查到东莞取决于当前部署的 `data/gis` 运行数据是否收录了东莞。请求格式本身如上；如果返回 `matched: false` 且 `candidates: []`，表示当前运行数据未收录或名称路径不匹配。

## 行政层级与字段约定

当前数据包含 0-2 级行政区：

| deep | 含义 | 示例 |
| --- | --- | --- |
| `0` | 省级 / 直辖市级 | `广东省`、`北京市` |
| `1` | 地市级 / 直辖市重复市级 | `东莞市`、`北京市` |
| `2` | 区县级 | `东城区` |

通用 feature 字段：

```json
{
  "id": 110101,
  "pid": 1101,
  "deep": 2,
  "name": "东城区",
  "ext_path": "北京市 北京市 东城区",
  "center_lng": 116.41637,
  "center_lat": 39.92855,
  "source_crs": "unknown",
  "target_crs": "EPSG:4326",
  "source_file": "areacity_level2.geojson",
  "geometry_type": "Polygon",
  "geometry_exists": true
}
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `id` | 稳定行政区 ID。拿边界时使用这个字段。 |
| `pid` | 父级 ID。顶级通常为 `0`。 |
| `deep` | 行政层级，见上表。 |
| `name` | 当前层级名称。 |
| `ext_path` | 文本路径，主要用于展示或搜索命中说明。注意它是字符串，不是结构化对象。 |
| `center_lng` / `center_lat` | 中心点经纬度，可能为 `null`。 |
| `target_crs` | 运行态输出坐标系，前端地图按 WGS84/EPSG:4326 使用。 |
| `geometry_type` | 边界类型，常见为 `Polygon` 或 `MultiPolygon`。 |
| `geometry_exists` | 是否有边界数据。为 `false` 时即使命中 feature，也可能拿不到有效 geometry。 |

## 接口职责总览

| 接口 | 主要用途 | 是否消歧 | 是否返回边界 geometry |
| --- | --- | --- | --- |
| `GET /api/gis/status` | 检查 GIS 引擎、数据、缓存状态 | 否 | 否 |
| `GET /api/gis/search` | 地名模糊搜索、候选列表、输入提示 | 否 | 否 |
| `GET /api/gis/resolve` | 按行政路径消歧，拿稳定 `feature.id` | 是 | 否 |
| `GET /api/gis/children` | 读取行政树子节点 | 否 | 否 |
| `GET /api/gis/boundary/by-id` | 按 `feature_id` 读取边界 GeoJSON | 不需要，ID 已唯一 | 是 |
| `GET /api/gis/query/point` | 查询坐标点落在哪些行政区内 | 空间命中 | 否 |
| `GET /api/gis/query/point-with-tolerance` | 点不在面内时，按容差找附近行政区 | 空间命中 | 否 |
| `POST /api/gis/query/geometry` | 查询一个 Polygon/MultiPolygon 与哪些行政区相交 | 空间命中 | 否 |

## `GET /api/gis/search`

### 作用

用于地名模糊搜索。适合做搜索框候选、自动补全、人工选择列表。

它会匹配：

- `name`
- `ext_path`

它不负责唯一性判断，也不会因为 `q=东城区` 自动知道你要哪个父层级下的东城区。

### 请求

```http
GET /api/gis/search?q=北京
GET /api/gis/search?q=东城区&deep=2
```

查询参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `q` | string | 是 | 搜索关键词，最少 1 个字符。 |
| `deep` | number | 否 | 限制行政层级，可取 `0`、`1`、`2`。 |

### 响应

```json
{
  "success": true,
  "items": [
    {
      "id": 11,
      "pid": 0,
      "deep": 0,
      "name": "北京市",
      "ext_path": "北京市",
      "center_lng": 116.4074,
      "center_lat": 39.9042,
      "source_crs": "unknown",
      "target_crs": "EPSG:4326",
      "source_file": "areacity_level0.geojson",
      "geometry_type": "MultiPolygon",
      "geometry_exists": true
    }
  ]
}
```

### 前端注意事项

- `search` 返回的是候选数组，不保证只有一个结果。
- 同名或短名查询时，不要默认取第一个结果。
- 如果用户只是输入了一个地名，比如 `东城区`，应该把候选展示给用户，或者继续要求父层级。
- 如果业务已经知道父层级，例如 `北京市 / 北京市 / 东城区`，应直接调用 `resolve`。

## `GET /api/gis/resolve`

### 作用

用于把行政路径解析成唯一 feature。它是前端做“最终确认”的接口。

适合这些场景：

- 用户从省/市/区三级选择器里选了完整路径。
- 搜索结果里需要确认某个候选是否唯一。
- 前端要拿边界，但手上只有行政区名称。

### 请求方式 1：结构化参数

```http
GET /api/gis/resolve?province=北京市&city=北京市&county=东城区
GET /api/gis/resolve?province=广东省&city=东莞市
```

查询参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `province` | string | 否 | 省级名称。 |
| `city` | string | 否 | 地市级名称。 |
| `county` | string | 否 | 区县级名称。 |

### 请求方式 2：路径参数

```http
GET /api/gis/resolve?path=北京市/北京市/东城区
GET /api/gis/resolve?path=北京市/东城区
GET /api/gis/resolve?path=北京市>北京市>东城区
```

查询参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `path` | string | 否 | 行政路径。支持 `/` 分隔，也支持 `>` 分隔。 |

直辖市支持短路径。例如存储路径是 `北京市 / 北京市 / 东城区`，请求 `path=北京市/东城区` 也可以匹配。

### 成功且唯一匹配

```json
{
  "success": true,
  "matched": true,
  "ambiguous": false,
  "feature": {
    "id": 110101,
    "pid": 1101,
    "deep": 2,
    "name": "东城区",
    "ext_path": "北京市 北京市 东城区",
    "center_lng": 116.41637,
    "center_lat": 39.92855,
    "source_crs": "unknown",
    "target_crs": "EPSG:4326",
    "source_file": "areacity_level2.geojson",
    "geometry_type": "Polygon",
    "geometry_exists": true,
    "path": [
      {"id": 11, "name": "北京市", "deep": 0},
      {"id": 1101, "name": "北京市", "deep": 1},
      {"id": 110101, "name": "东城区", "deep": 2}
    ],
    "path_names": {
      "province": "北京市",
      "city": "北京市",
      "county": "东城区"
    }
  },
  "candidates": []
}
```

### 有多个候选，后端不猜

```json
{
  "success": true,
  "matched": false,
  "ambiguous": true,
  "feature": null,
  "candidates": [
    {
      "id": 11,
      "pid": 0,
      "deep": 0,
      "name": "北京市",
      "ext_path": "北京市",
      "path": [
        {"id": 11, "name": "北京市", "deep": 0}
      ],
      "path_names": {
        "province": "北京市",
        "city": null,
        "county": null
      }
    },
    {
      "id": 1101,
      "pid": 11,
      "deep": 1,
      "name": "北京市",
      "ext_path": "北京市 北京市",
      "path": [
        {"id": 11, "name": "北京市", "deep": 0},
        {"id": 1101, "name": "北京市", "deep": 1}
      ],
      "path_names": {
        "province": "北京市",
        "city": "北京市",
        "county": null
      }
    }
  ]
}
```

### 没有匹配

```json
{
  "success": true,
  "matched": false,
  "ambiguous": false,
  "feature": null,
  "candidates": []
}
```

### 前端判断逻辑

```ts
if (data.matched && data.feature) {
  // 使用 data.feature.id 请求 boundary/by-id
} else if (data.ambiguous) {
  // 展示 candidates，让用户补充父层级或手动选择
} else {
  // 提示未找到
}
```

### 为什么 `q=东城区` 不带父层级不可靠？

因为 `search` 是模糊搜索，不是行政路径解析。中国行政区里重名、简称、直辖市重复层级都很常见。

正确做法：

- 输入提示：用 `search?q=东城区&deep=2`。
- 最终确认：用 `resolve?province=北京市&city=北京市&county=东城区`。
- 拿边界：用 `boundary/by-id?feature_id=110101`。

## `GET /api/gis/boundary/by-id`

### 作用

按稳定的 `feature_id` 返回行政区边界。这个接口会返回完整 GeoJSON geometry，适合地图绘制。

### 请求

```http
GET /api/gis/boundary/by-id?feature_id=110101
```

查询参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `feature_id` | number | 是 | `resolve`、`search` 或 `children` 返回的 `id`。必须大于等于 1。 |

### 响应

```json
{
  "feature": {
    "id": 110101,
    "pid": 1101,
    "deep": 2,
    "name": "东城区",
    "ext_path": "北京市 北京市 东城区",
    "center_lng": 116.41637,
    "center_lat": 39.92855,
    "source_crs": "unknown",
    "target_crs": "EPSG:4326",
    "source_file": "areacity_level2.geojson",
    "geometry_type": "Polygon",
    "geometry_exists": true
  },
  "geometry": {
    "type": "Polygon",
    "coordinates": [
      [
        [116.38, 39.86],
        [116.45, 39.86],
        [116.45, 39.97],
        [116.38, 39.97],
        [116.38, 39.86]
      ]
    ]
  }
}
```

实际坐标数组会比示例长很多。

### 错误

未找到 ID 时：

```http
HTTP/1.1 404 Not Found
```

```json
{
  "detail": "Feature not found"
}
```

### 前端注意事项

- 这是最可能返回大响应的接口。前端应对 `feature_id` 做缓存，避免重复请求同一个边界。
- 响应里的 `geometry` 是 GeoJSON Geometry，不是完整 FeatureCollection。绘图时通常需要前端自己包装成 GeoJSON Feature：

```ts
const geojsonFeature = {
  type: "Feature",
  properties: response.feature,
  geometry: response.geometry
}
```

- 坐标顺序是 `[lng, lat]`，不是 `[lat, lng]`。

## `GET /api/gis/children`

### 作用

读取行政树节点。适合做省/市/区级联选择器。

### 请求

```http
GET /api/gis/children
GET /api/gis/children?deep=0
GET /api/gis/children?parent_id=44
GET /api/gis/children?parent_id=44&deep=1
```

查询参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `parent_id` | number | 否 | 父级 ID。省级的父级通常是 `0`。 |
| `deep` | number | 否 | 限制返回层级，可取 `0`、`1`、`2`。 |

### 响应

```json
{
  "success": true,
  "items": [
    {
      "id": 44,
      "pid": 0,
      "deep": 0,
      "name": "广东省",
      "ext_path": "广东省",
      "center_lng": 113.27,
      "center_lat": 23.13,
      "source_crs": "unknown",
      "target_crs": "EPSG:4326",
      "source_file": "areacity_level0.geojson",
      "geometry_type": "MultiPolygon",
      "geometry_exists": true
    }
  ]
}
```

### 前端注意事项

- 做级联选择器时，推荐先 `children?deep=0` 获取省级。
- 用户选中某个省后，用 `children?parent_id=<省 id>` 获取下级。
- 只展示行政树时，不需要请求边界。

## `GET /api/gis/query/point`

### 作用

查询一个坐标点落在哪些行政区内。通常会返回从省到市到区县的多个命中。

### 请求

```http
GET /api/gis/query/point?lng=116.4074&lat=39.9042
```

查询参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `lng` | number | 是 | 经度，范围 `-180` 到 `180`。 |
| `lat` | number | 是 | 纬度，范围 `-90` 到 `90`。 |

### 响应

```json
{
  "result": [
    {
      "id": 11,
      "pid": 0,
      "deep": 0,
      "name": "北京市",
      "ext_path": "北京市",
      "center_lng": 116.4074,
      "center_lat": 39.9042,
      "source_crs": "unknown",
      "target_crs": "EPSG:4326",
      "source_file": "areacity_level0.geojson",
      "geometry_type": "MultiPolygon",
      "geometry_exists": true
    }
  ],
  "stats": {
    "query_count": 1,
    "envelope_hit_count": 10,
    "exact_hit_count": 1,
    "nearest_hit_count": 0,
    "io_reads": 10,
    "cache_hit_count": 0,
    "cache_miss_count": 10,
    "cache_eviction_count": 0
  }
}
```

### 前端注意事项

- 这个接口只返回命中的 feature 元数据，不返回边界 geometry。
- 如果需要展示边界，再拿命中的 `id` 调 `boundary/by-id`。
- 点在边界线上或数据精度不足时，可能没有命中；这种情况可以考虑 `point-with-tolerance`。

## `GET /api/gis/query/point-with-tolerance`

### 作用

先执行点内查询；如果点没有直接命中任何行政区，则在给定容差内查找最近的行政区。适合处理用户点选偏移、边界附近、GPS 有误差的情况。

### 请求

```http
GET /api/gis/query/point-with-tolerance?lng=116.4074&lat=39.9042&tolerance_metre=5000
```

查询参数：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `lng` | number | 是 | - | 经度，范围 `-180` 到 `180`。 |
| `lat` | number | 是 | - | 纬度，范围 `-90` 到 `90`。 |
| `tolerance_metre` | number | 否 | `2500` | 容差，单位米，必须大于等于 `0`。 |

### 响应

如果直接命中，响应与 `query/point` 类似。

如果没有直接命中但找到附近行政区，返回项会额外带距离字段：

```json
{
  "result": [
    {
      "id": 110101,
      "pid": 1101,
      "deep": 2,
      "name": "东城区",
      "ext_path": "北京市 北京市 东城区",
      "point_distance": 123.45,
      "point_distance_id": 110101
    }
  ],
  "stats": {
    "query_count": 1,
    "envelope_hit_count": 0,
    "exact_hit_count": 0,
    "nearest_hit_count": 1,
    "io_reads": 8,
    "cache_hit_count": 0,
    "cache_miss_count": 8,
    "cache_eviction_count": 0
  }
}
```

### 前端注意事项

- `point_distance` 单位是米。
- 不建议把 `tolerance_metre` 设得过大。容差越大，候选越多，查询越慢。
- 如果业务要求严格行政区内命中，用 `query/point`；如果业务允许“附近归属”，用 `point-with-tolerance`。

## `POST /api/gis/query/geometry`

### 作用

查询一个 GeoJSON 面与哪些行政区相交。适合矩形框选、多边形选区、地图视口粗筛等。

### 请求

```http
POST /api/gis/query/geometry
Content-Type: application/json
```

```json
{
  "geometry": {
    "type": "Polygon",
    "coordinates": [
      [
        [116.35, 39.86],
        [116.48, 39.86],
        [116.48, 39.96],
        [116.35, 39.96],
        [116.35, 39.86]
      ]
    ]
  }
}
```

请求体：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `geometry` | object | 是 | GeoJSON Geometry。只支持 `Polygon` 和 `MultiPolygon`。 |

### 响应

```json
{
  "result": [
    {
      "id": 110101,
      "pid": 1101,
      "deep": 2,
      "name": "东城区",
      "ext_path": "北京市 北京市 东城区",
      "center_lng": 116.41637,
      "center_lat": 39.92855,
      "source_crs": "unknown",
      "target_crs": "EPSG:4326",
      "source_file": "areacity_level2.geojson",
      "geometry_type": "Polygon",
      "geometry_exists": true
    }
  ],
  "stats": {
    "query_count": 1,
    "envelope_hit_count": 12,
    "exact_hit_count": 1,
    "nearest_hit_count": 0,
    "io_reads": 12,
    "cache_hit_count": 0,
    "cache_miss_count": 12,
    "cache_eviction_count": 0
  }
}
```

### 错误

`geometry.type` 不是 `Polygon` 或 `MultiPolygon`：

```http
HTTP/1.1 422 Unprocessable Entity
```

```json
{
  "detail": "Only Polygon and MultiPolygon are supported"
}
```

缺少 `coordinates`：

```http
HTTP/1.1 422 Unprocessable Entity
```

```json
{
  "detail": "GeoJSON geometry must include coordinates"
}
```

### 前端注意事项

- 坐标顺序必须是 `[lng, lat]`。
- Polygon 首尾点应闭合，即最后一个点等于第一个点。
- 这个接口返回相交行政区的元数据，不返回每个行政区的完整边界。
- 如果需要绘制命中的行政区边界，需要再按 `id` 调 `boundary/by-id`。

## `GET /api/gis/status`

### 作用

检查 GIS 引擎是否加载、数据规模、缓存状态和运行文件路径。适合调试、健康检查、后台状态页。

### 请求

```http
GET /api/gis/status
```

### 响应

```json
{
  "loaded": true,
  "mode": "lowmem-sqlite",
  "feature_count": 3210,
  "subgeometry_count": 10000,
  "features_with_multiple_parts": 123,
  "split_mode": "unknown",
  "source_crs": "unknown",
  "target_crs": "EPSG:4326",
  "storage_format": "unknown",
  "grid_factor": 100,
  "subgrid_factor": 100,
  "cache_max_items": 1024,
  "cache_current_items": 10,
  "cache_hit_count": 20,
  "cache_miss_count": 30,
  "cache_eviction_count": 0,
  "index_path": "/app/data/gis/areacity.index.sqlite",
  "features_path": "/app/data/gis/areacity.features.jsonl",
  "geometry_path": "/app/data/gis/areacity.subgeom.bin"
}
```

具体数字以部署环境为准。

### 前端注意事项

- 普通用户页面一般不需要调用这个接口。
- 可用于判断 GIS 数据是否正确挂载：`index_path`、`features_path`、`geometry_path` 应指向 `data/gis`。

## 常见业务用法

### 查“东莞市”的边界

第一步，解析行政路径：

```http
GET /api/gis/resolve?province=广东省&city=东莞市
```

第二步，如果当前部署数据收录了东莞，并且返回：

```json
{
  "success": true,
  "matched": true,
  "ambiguous": false,
  "feature": {
    "id": 441900,
    "name": "东莞市"
  },
  "candidates": []
}
```

第三步，请求边界：

```http
GET /api/gis/boundary/by-id?feature_id=441900
```

注意：

- 这里的 `441900` 是示例 ID，前端必须使用 `resolve` 实际返回的 `feature.id`。
- 如果返回 `matched: false`、`ambiguous: false`、`candidates: []`，说明当前运行数据没有匹配到 `广东省 / 东莞市`，不是前端请求格式错误。

### 做行政区搜索框

用户输入时：

```http
GET /api/gis/search?q=东莞
```

展示 `items`，建议展示：

- `name`
- `ext_path`
- `deep`

用户选择后：

- 如果选择项已有明确 `id`，可以直接用这个 `id` 请求边界。
- 如果业务要求必须按父层级确认，使用 `resolve` 再确认一次。

### 做省市区级联选择器

读取省级：

```http
GET /api/gis/children?deep=0
```

读取某个省的下级：

```http
GET /api/gis/children?parent_id=44
```

读取某个市的区县：

```http
GET /api/gis/children?parent_id=4401
```

用户选完后，前端已经拿到最终节点 `id`，可以直接请求：

```http
GET /api/gis/boundary/by-id?feature_id=<最终节点 id>
```

### 查询一个经纬度属于哪里

```http
GET /api/gis/query/point?lng=116.4074&lat=39.9042
```

前端可以按 `deep` 分组展示：

- `deep=0`：省级
- `deep=1`：市级
- `deep=2`：区县级

## 错误与参数校验

FastAPI 会对部分参数做自动校验：

| 场景 | HTTP 状态码 |
| --- | --- |
| 缺少必填参数，例如 `search` 没有 `q` | `422` |
| `lng` 超出 `-180..180` | `422` |
| `lat` 超出 `-90..90` | `422` |
| `deep` 不在 `0..2` | `422` |
| `feature_id` 小于 `1` | `422` |
| `boundary/by-id` 找不到 feature | `404` |
| `query/geometry` 传入不支持的 geometry type | `422` |

前端建议：

- 对 `422` 展示“参数不合法”或在开发环境打印 `detail`。
- 对 `404` 展示“边界不存在或数据未收录”。
- 对 `resolve` 的未匹配不要当 HTTP 错误处理；它会返回 `200`，通过 `matched` / `ambiguous` 判断业务状态。

## 性能与缓存建议

- `search`、`resolve`、`children` 返回元数据，通常较轻。
- `boundary/by-id` 可能返回较大的 GeoJSON，前端应按 `feature_id` 缓存。
- `query/geometry` 的成本取决于传入 polygon 的范围和复杂度。范围越大、点越多，查询越重。
- `point-with-tolerance` 的成本取决于 `tolerance_metre`。容差越大，候选越多。
- 如果只是展示行政树，不要请求边界。
- 如果只是定位点属于哪里，不要请求边界，除非后续需要地图绘制。

## 运行态数据依赖

生产运行时 GIS API 只读取 `data/gis/`。部署后端时上传这个目录即可：

```text
data/gis/areacity.features.jsonl
data/gis/areacity.index.sqlite
data/gis/areacity.subgeom.bin
data/gis/areacity.meta.json
data/gis/areacity.build_manifest.json
```

本地当前目录大小约为：

```text
data/gis                              48M
data/gis/areacity.features.jsonl      220K
data/gis/areacity.index.sqlite        1.8M
data/gis/areacity.subgeom.bin         46M
data/gis/areacity.meta.json           4.0K
data/gis/areacity.build_manifest.json 4.0K
```

API 运行时不读取 `data/geo/`。如果以后需要重新生成 GIS 资产，应单独运行预处理脚本，然后把生成后的运行态文件放入 `data/gis/`。

如需把 GIS 数据放在仓库外，可设置：

```bash
GIS_DATA_DIR=/absolute/path/to/data/gis
```

## 前端接入检查清单

- 搜索框候选用 `search`，最终消歧用 `resolve`。
- 查边界前尽量先拿稳定 `feature.id`。
- 不要把 `search?q=某地名` 的第一个结果直接当唯一结果。
- 绘图坐标按 `[lng, lat]` 处理。
- `boundary/by-id` 返回的是 GeoJSON Geometry；如果地图库需要 Feature，前端自行包装。
- 缓存边界响应，避免重复拉取大 GeoJSON。
- `resolve` 返回 `200` 不代表一定匹配成功，要看 `matched` 和 `ambiguous`。
- 服务器部署只需要带 `data/gis/`，不需要带旧的 `data/geo/`。
