# Toponyms Map API

## Contract

The public toponyms APIs deliberately separate coordinates from place names.

- Coordinate responses return only `id`, `longitude`, and `latitude`.
- Name responses return only name strings.
- The backend does not provide `id -> name` or `name -> id/coordinate` lookup APIs.
- `data/toponyms.db` is not exposed through the generic `/sql` database mapping.

This is intentional. Do not merge these fields into one response, even for GeoJSON.

## Coordinates

```http
GET /api/toponyms/points
```

This MVP endpoint has no query parameters. It returns all natural-village point
coordinates in one response. Query parameters such as `bbox`, `zoom`, and
`limit` are rejected so callers do not accidentally keep using a tiled loading
contract.

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

## Name Samples

```http
GET /api/toponyms/names/sample?q=黄&limit=20
```

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

The runtime API can work without the extra indexes, but filtering the full
`data/toponyms.db` by natural-village type and ordering by id benefits from an
index. Create the recommended indexes during a maintenance window:

```bash
.venv/bin/python -m scripts.toponyms.ensure_indexes --db data/toponyms.db
```

The helper creates:

```sql
CREATE INDEX IF NOT EXISTS idx_single_type_id
ON single(place_type_code, id);

CREATE INDEX IF NOT EXISTS idx_single_type_name
ON single(place_type_code, standard_name);
```

It also runs `ANALYZE`.
