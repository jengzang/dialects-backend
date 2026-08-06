# Toponyms Map API

## Contract

The public toponyms APIs deliberately separate coordinates from place names.

- Coordinate responses return only `id`, `longitude`, and `latitude`.
- Name responses return only name strings, or division-name tree nodes that
  contain name strings.
- The details response is the only `id -> full record` lookup, and it is capped
  at 10 IDs per request.
- `data/toponyms.db` is not exposed through the generic `/sql` database mapping.

This is intentional. Do not merge these fields into one response, even for GeoJSON.

## Coordinates

```http
GET /api/toponyms/points?q=黄&match_mode=prefix&limit=0
```

This endpoint returns point coordinates for matching names. It defaults to
natural-village points (`place_type_code=22200`) and never returns the matched
names or place type labels.

For the frontend distribution map, pass `limit=0` so the response contains the
complete point set for the current query conditions. `limit` is retained for
diagnostics and guarded requests, but using a positive value intentionally
truncates the point set and is not suitable for distribution statistics.

Query parameters:

| Name | Required | Default | Description |
| --- | --- | --- | --- |
| `q` | yes | - | Name query text. Blank values are rejected. |
| `match_mode` | no | `prefix` | One of `prefix`, `suffix`, `exact`, `contains`. |
| `limit` | no | `5000` | Maximum returned points. `0` means no limit. Upper bound: `2000000`. Frontend distribution views should pass `0`. |
| `bbox` | no | - | Optional `minLng,minLat,maxLng,maxLat` filter after name match. |
| `zoom` | no | - | Optional `0..24`; accepted for frontend state, currently only validated. |
| `place_type_code` | no | `22200` | Numeric place type filter. Examples: `22200` rural residential points, `21610` administrative villages, `27610` village committees. |

Response:

```json
{
  "items": [
    {
      "id": "10007e71a4c2821a4b0f728b41a2abb4",
      "longitude": 113.7347038,
      "latitude": 23.0417921
    }
  ],
  "count": 1,
  "truncated": false,
  "next": null
}
```

The response still does not include names, area codes, or place type labels.

## Names

```http
GET /api/toponyms/names?q=黄&match_mode=prefix&limit=20
```

This endpoint returns distinct matched names. It defaults to natural-village
names (`place_type_code=22200`) and supports the same matching semantics as
`/api/toponyms/points`.

Query parameters:

| Name | Required | Default | Description |
| --- | --- | --- | --- |
| `q` | yes | - | Name query text. Blank values are rejected. |
| `match_mode` | no | `prefix` | One of `prefix`, `suffix`, `exact`, `contains`. |
| `limit` | no | `20` | Maximum returned names. `0` means no limit. Upper bound: `2000000`. |
| `include_division_tree` | no | `false` | When `true`, return nested division-name nodes instead of a flat name array. |
| `bbox` | no | - | Optional `minLng,minLat,maxLng,maxLat` filter after name match. The response still omits coordinates. |
| `parent_path` | no | - | Lazy tree expansion path. Repeat the parameter once per division name, for example `parent_path=广东省&parent_path=广州市`. |
| `page` | no | `1` | Lazy leaf-name page number. Used only when `parent_path` points to level 4. |
| `page_size` | no | `100` | Lazy leaf-name page size. Upper bound: `500`. |
| `place_type_code` | no | `22200` | Numeric place type filter. Examples: `22200`, `21610`, `27610`. |

Flat response:

```json
{
  "items": ["黄村", "黄泥村"]
}
```

Tree response:

```http
GET /api/toponyms/names?q=村&match_mode=suffix&include_division_tree=true
```

Small result sets return a complete tree in `mode=full`. The tree mode ignores
`limit` for completeness; if the matching result is too large, the same endpoint
falls back to lazy expansion instead.

```json
{
  "mode": "full",
  "items": [
    {
      "name": "广东省",
      "level": 1,
      "names": [],
      "children": [
        {
          "name": "广州市",
          "level": 2,
          "names": [],
          "children": [
            {
              "name": "越秀街道",
              "level": 4,
              "names": ["黄村"],
              "children": []
            }
          ]
        }
      ]
    }
  ],
  "levels": 4
}
```

Large result sets return `mode=lazy_fallback`, inspired by the `/sql/tree/full`
fallback style. The initial response includes the first two administrative
levels so the frontend can render an expandable tree without transferring all
leaf names at once.

```json
{
  "mode": "lazy_fallback",
  "reason": "tree_result_too_large",
  "threshold": 5000,
  "filtered_count": 59739,
  "levels": 4,
  "lazy_bootstrap": [
    {
      "name": "广东省",
      "level": 1,
      "children": [
        {"name": "广州市", "level": 2}
      ]
    }
  ]
}
```

Expand a non-leaf node with the same endpoint and repeated `parent_path`
parameters:

```http
GET /api/toponyms/names?q=黄&match_mode=prefix&include_division_tree=true&parent_path=广东省
```

```json
{
  "mode": "lazy",
  "level": 2,
  "parent_path": ["广东省"],
  "children": [
    {"name": "广州市", "level": 2}
  ],
  "has_more": false
}
```

When `parent_path` reaches level 4, the endpoint returns paginated matched place
names for that leaf division:

```http
GET /api/toponyms/names?q=黄&match_mode=prefix&include_division_tree=true&parent_path=广东省&parent_path=广州市&parent_path=广州市辖区&parent_path=越秀街道&page=1&page_size=100
```

```json
{
  "mode": "lazy",
  "level": 4,
  "parent_path": ["广东省", "广州市", "广州市辖区", "越秀街道"],
  "names": ["黄村", "黄屋"],
  "page": 1,
  "page_size": 100,
  "has_more": false
}
```

Lazy pagination is by distinct `(name, area_code)` records under the selected
level-4 administrative path. The response exposes only the public name strings,
not IDs, coordinates, area codes, division codes, or ordering keys.

Tree nodes intentionally expose only division names, division levels, child
nodes, and matched name strings. They do not expose division codes, toponym IDs,
coordinates, area codes, or ordering keys.

The response never includes IDs, coordinates, area codes, or ordering keys.

## Details

```http
GET /api/toponyms/details?ids=10007e71a4c2821a4b0f728b41a2abb4,another-id
```

This endpoint returns full records for explicit IDs. It is intentionally capped
at 10 IDs per request.

Query parameters:

| Name | Required | Description |
| --- | --- | --- |
| `ids` | yes | Comma-separated IDs or repeated `ids` parameters. Empty values are ignored. At most 10 unique IDs. |

Response:

```json
{
  "items": [
    {
      "id": "10007e71a4c2821a4b0f728b41a2abb4",
      "name": "黄村",
      "place_type": "农村居民点",
      "place_type_code": "22200",
      "longitude": 113.7347038,
      "latitude": 23.0417921,
      "division_path": [
        {"name": "广东省", "level": 1},
        {"name": "广州市", "level": 2}
      ]
    }
  ],
  "count": 1
}
```

Missing IDs are skipped. The response does not expose `area_code` or division
codes.

## Divisions

```http
GET /api/toponyms/divisions?parent_code=44
```

Response:

```json
{
  "items": [
    {
      "code": "4401",
      "name": "广州市",
      "level": 2,
      "single_count": 35365
    }
  ]
}
```

This endpoint omits division centroid coordinates.

## Index Maintenance

The runtime API can work without the extra indexes, but name matching and
optional bbox filtering are much better with indexes. Create the recommended
indexes during a maintenance window:

```bash
.venv/bin/python -m scripts.toponyms.ensure_indexes --db data/toponyms.db
```

The helper creates:

```sql
CREATE INDEX IF NOT EXISTS idx_single_type_id
ON single(place_type_code, id);

CREATE INDEX IF NOT EXISTS idx_single_type_name_id
ON single(place_type_code, standard_name, id);

CREATE INDEX IF NOT EXISTS idx_single_type_name_area
ON single(place_type_code, standard_name, area_code);

CREATE INDEX IF NOT EXISTS idx_single_type_lng_lat_id
ON single(place_type_code, longitude, latitude, id);
```

It also runs `ANALYZE`.
