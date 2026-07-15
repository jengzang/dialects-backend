# Toponyms Map API

## Contract

The public toponyms APIs deliberately separate coordinates from place names.

- Coordinate responses return only `id`, `longitude`, and `latitude`.
- Name responses return only name strings, or division-name tree nodes that
  contain name strings.
- The backend does not provide `id -> name` or `name -> id/coordinate` lookup APIs.
- `data/toponyms.db` is not exposed through the generic `/sql` database mapping.

This is intentional. Do not merge these fields into one response, even for GeoJSON.

## Coordinates

```http
GET /api/toponyms/points?q=黄&match_mode=prefix&limit=5000
```

This endpoint returns point coordinates for natural villages whose names match
the query. It never returns the matched names.

Query parameters:

| Name | Required | Default | Description |
| --- | --- | --- | --- |
| `q` | yes | - | Name query text. Blank values are rejected. |
| `match_mode` | no | `prefix` | One of `prefix`, `suffix`, `exact`, `contains`. |
| `limit` | no | `5000` | Maximum returned points. `0` means no limit. |
| `bbox` | no | - | Optional `minLng,minLat,maxLng,maxLat` filter after name match. |
| `zoom` | no | - | Optional `0..24`; accepted for frontend state, currently only validated. |

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
GET /api/toponyms/names/?q=黄&match_mode=prefix&limit=20
```

This endpoint returns distinct matched natural-village names. It supports the
same matching semantics as `/api/toponyms/points`.

Query parameters:

| Name | Required | Default | Description |
| --- | --- | --- | --- |
| `q` | yes | - | Name query text. Blank values are rejected. |
| `match_mode` | no | `prefix` | One of `prefix`, `suffix`, `exact`, `contains`. |
| `limit` | no | `20` | Maximum returned names. `0` means no limit. |
| `include_division_tree` | no | `false` | When `true`, return nested division-name nodes instead of a flat name array. |

Flat response:

```json
{
  "items": ["黄村", "黄泥村"]
}
```

Tree response:

```http
GET /api/toponyms/names/?q=村&match_mode=suffix&include_division_tree=true&limit=20
```

```json
{
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
  ]
}
```

Tree nodes intentionally expose only division names, division levels, child
nodes, and matched name strings. They do not expose division codes, toponym IDs,
coordinates, area codes, or ordering keys.

## Name Samples

```http
GET /api/toponyms/names/sample?q=黄&match_mode=prefix&limit=20
```

This remains a compatibility alias for flat name samples. `match_mode` supports
the same four values as `/api/toponyms/points`. `limit=0` means no limit.

Response:

```json
{
  "items": ["黄村", "黄泥村"]
}
```

The response never includes IDs, coordinates, area codes, or ordering keys.

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
