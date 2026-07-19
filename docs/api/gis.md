# GIS API

The new GIS API is served under `/api/gis/**` by the GIS worker.

## Resolve administrative features

Use `GET /api/gis/resolve` to convert an administrative path into a stable
`feature.id`. Use the returned ID with `/api/gis/boundary/by-id`.

Supported query forms:

```text
GET /api/gis/resolve?province=北京市&city=北京市&county=东城区
GET /api/gis/resolve?path=北京市/北京市/东城区
GET /api/gis/resolve?path=北京市/东城区
```

The short two-part municipality form, such as `北京市/东城区`, is accepted when
the stored path repeats the municipality at province and city level.

Successful unique match:

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

Ambiguous match:

```json
{
  "success": true,
  "matched": false,
  "ambiguous": true,
  "feature": null,
  "candidates": []
}
```

Not found:

```json
{
  "success": true,
  "matched": false,
  "ambiguous": false,
  "feature": null,
  "candidates": []
}
```

## Read boundary by feature ID

```text
GET /api/gis/boundary/by-id?feature_id=110101
```

Returns the feature metadata and GeoJSON geometry for the requested feature.

## Other GIS endpoints

```text
GET  /api/gis/status
GET  /api/gis/search?q=北京&deep=0
GET  /api/gis/children?parent_id=11&deep=1
GET  /api/gis/query/point?lng=116.4074&lat=39.9042
GET  /api/gis/query/point-with-tolerance?lng=116.4074&lat=39.9042&tolerance_metre=5000
POST /api/gis/query/geometry
```
