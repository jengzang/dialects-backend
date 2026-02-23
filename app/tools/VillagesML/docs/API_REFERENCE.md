# API Reference

Complete reference for the Guangdong Province Natural Village Analysis System API.

**Base URL:** `http://localhost:8000`
**Documentation:** `http://localhost:8000/docs` (Swagger UI)
**API Version:** 1.0.0

---

## Table of Contents

1. [Endpoint Overview](#endpoint-overview)
2. [Precomputed Endpoints](#precomputed-endpoints)
3. [Online Compute Endpoints](#online-compute-endpoints)
4. [Data Models](#data-models)
5. [Error Responses](#error-responses)
6. [Common Patterns](#common-patterns)

---

## Endpoint Overview

### Precomputed Endpoints (Fast, <100ms)

These endpoints query precomputed results from the database:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/character/frequency/global` | GET | Global character frequency statistics |
| `/api/character/frequency/regional` | GET | Regional character frequency statistics |
| `/api/character/tendency/by-region` | GET | Character tendency for specific region |
| `/api/character/tendency/by-char` | GET | Character tendency across regions |
| `/api/village/search` | GET | Search villages by keyword |
| `/api/village/search/detail` | GET | Get village detail information |
| `/api/metadata/stats/overview` | GET | System overview statistics |
| `/api/metadata/stats/tables` | GET | Database table information |

### Online Compute Endpoints (Slower, >1s)

These endpoints perform real-time analysis:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/compute/clustering/run` | POST | Run clustering analysis |
| `/api/compute/clustering/scan` | POST | Scan multiple k values |
| `/api/compute/semantic/cooccurrence` | POST | Analyze semantic co-occurrence |
| `/api/compute/semantic/network` | POST | Build semantic network |
| `/api/compute/features/extract` | POST | Extract village features |
| `/api/compute/features/aggregate` | POST | Aggregate regional features |
| `/api/compute/subset/cluster` | POST | Cluster village subset |
| `/api/compute/subset/compare` | POST | Compare two village groups |
| `/api/compute/cache/stats` | GET | Get cache statistics |
| `/api/compute/cache/clear` | POST | Clear cache |

### Utility Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API root information |
| `/health` | GET | Health check |

---

## Precomputed Endpoints

### 1. Global Character Frequency

**GET** `/api/character/frequency/global`

Get global character frequency statistics from precomputed data.

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `run_id` | string | No | "default" | Analysis run ID |
| `top_n` | integer | No | 100 | Return top N characters (1-1000) |
| `min_frequency` | integer | No | null | Minimum frequency filter |

**Response:** `List[CharFrequency]`

```json
[
  {
    "character": "村",
    "frequency": 125430,
    "village_count": 98234,
    "rank": 1
  },
  {
    "character": "新",
    "frequency": 45678,
    "village_count": 34567,
    "rank": 2
  }
]
```

**Error Responses:**
- `404`: No data found for specified run_id

**Performance:** <50ms

---

### 2. Regional Character Frequency

**GET** `/api/character/frequency/regional`

Get character frequency statistics by region.

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `run_id` | string | No | "default" | Analysis run ID |
| `region_level` | string | Yes | - | Region level: "city", "county", or "township" |
| `region_name` | string | No | null | Specific region name (returns all if not specified) |
| `top_n` | integer | No | 50 | Top N characters per region (1-500) |

**Response:** `List[RegionalCharFrequency]`

```json
[
  {
    "region_name": "广州市",
    "character": "村",
    "frequency": 12543,
    "rank": 1
  },
  {
    "region_name": "广州市",
    "character": "新",
    "frequency": 4567,
    "rank": 2
  }
]
```

**Error Responses:**
- `404`: No data found for specified region_level/run_id
- `422`: Invalid region_level (must be city/county/township)

**Performance:** <100ms

---

### 3. Character Tendency by Region

**GET** `/api/character/tendency/by-region`

Get character tendency (lift, z-score) for a specific region.

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `run_id` | string | No | "default" | Analysis run ID |
| `region_level` | string | Yes | - | Region level: "city", "county", or "township" |
| `region_name` | string | Yes | - | Region name |
| `top_n` | integer | No | 50 | Top N characters (1-500) |
| `sort_by` | string | No | "z_score" | Sort field: "z_score", "lift", or "log_odds" |

**Response:** `List[CharTendency]`

```json
[
  {
    "character": "涌",
    "lift": 3.45,
    "log_odds": 1.23,
    "z_score": 5.67,
    "rank": 1
  }
]
```

**Error Responses:**
- `404`: No data found for specified region
- `422`: Invalid region_level or sort_by

**Performance:** <100ms

---

### 4. Character Tendency by Character

**GET** `/api/character/tendency/by-char`

Get tendency of a specific character across all regions.

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `run_id` | string | No | "default" | Analysis run ID |
| `character` | string | Yes | - | Single Chinese character |
| `region_level` | string | Yes | - | Region level: "city", "county", or "township" |

**Response:** `List[CharTendencyByRegion]`

```json
[
  {
    "region_name": "广州市",
    "lift": 2.34,
    "z_score": 4.56
  },
  {
    "region_name": "深圳市",
    "lift": 0.87,
    "z_score": -1.23
  }
]
```

**Error Responses:**
- `404`: No data found for specified character
- `422`: Invalid character (must be single character)

**Performance:** <100ms

---

### 5. Search Villages

**GET** `/api/village/search`

Search villages by keyword with optional region filters.

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | Yes | - | Village name keyword (min 1 char) |
| `city` | string | No | null | Filter by city |
| `county` | string | No | null | Filter by county |
| `township` | string | No | null | Filter by township |
| `limit` | integer | No | 20 | Number of results (1-100) |
| `offset` | integer | No | 0 | Pagination offset |

**Response:** `List[VillageBasic]`

```json
[
  {
    "village_name": "水口村",
    "city": "广州市",
    "county": "番禺区",
    "township": "石楼镇",
    "longitude": 113.456,
    "latitude": 23.123
  }
]
```

**Error Responses:**
- `422`: Invalid query parameter (min_length=1)

**Performance:** <200ms (depends on keyword selectivity)

---

### 6. Get Village Detail

**GET** `/api/village/search/detail`

Get detailed information for a specific village.

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `village_name` | string | Yes | - | Village name |
| `city` | string | Yes | - | City name |
| `county` | string | Yes | - | County name |
| `run_id` | string | No | "default" | Analysis run ID |

**Response:** `VillageDetail`

```json
{
  "basic_info": {
    "village_name": "水口村",
    "city": "广州市",
    "county": "番禺区",
    "township": "石楼镇",
    "longitude": 113.456,
    "latitude": 23.123
  },
  "semantic_tags": ["water", "settlement"],
  "suffix": "村",
  "cluster_id": 2,
  "spatial_features": {
    "knn_mean_distance": 0.45,
    "local_density": 12.3,
    "isolation_score": 0.23
  }
}
```

**Error Responses:**
- `404`: Village not found

**Performance:** <100ms

---

### 7. System Overview

**GET** `/api/metadata/stats/overview`

Get system-wide statistics.

**Query Parameters:** None

**Response:** `SystemOverview`

```json
{
  "total_villages": 285432,
  "total_cities": 21,
  "total_counties": 121,
  "total_townships": 1592,
  "unique_characters": 9209,
  "database_size_mb": 1734.56,
  "last_updated": "2026-02-20T10:30:00"
}
```

**Performance:** <50ms

---

### 8. Database Tables

**GET** `/api/metadata/stats/tables`

Get information about all database tables.

**Query Parameters:** None

**Response:** `List[TableInfo]`

```json
[
  {
    "table_name": "广东省自然村",
    "row_count": 285432,
    "size_mb": 0.0
  },
  {
    "table_name": "character_frequency",
    "row_count": 9209,
    "size_mb": 0.0
  }
]
```

**Performance:** <200ms

---

## Online Compute Endpoints

### 9. Run Clustering

**POST** `/api/compute/clustering/run`

Run clustering analysis on regional features.

**Request Body:**

```json
{
  "region_level": "county",
  "algorithm": "kmeans",
  "k": 4,
  "features": {
    "use_semantic": true,
    "use_morphology": true,
    "use_diversity": true
  },
  "preprocessing": {
    "standardize": true,
    "use_pca": false,
    "pca_n_components": 10
  },
  "region_filter": null,
  "random_state": 42
}
```

**Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `region_level` | string | Yes | "city", "county", or "township" |
| `algorithm` | string | Yes | "kmeans", "dbscan", or "gmm" |
| `k` | integer | Conditional | Number of clusters (required for kmeans/gmm) |
| `features` | object | Yes | Feature configuration |
| `preprocessing` | object | Yes | Preprocessing options |
| `region_filter` | array | No | List of region names to include |
| `random_state` | integer | No | Random seed (default: 42) |

**Response:** `ClusteringResult`

```json
{
  "run_id": "online_clustering_1708416000",
  "algorithm": "kmeans",
  "k": 4,
  "n_regions": 121,
  "execution_time_ms": 1234,
  "metrics": {
    "silhouette_score": 0.64,
    "davies_bouldin_index": 0.87,
    "calinski_harabasz_score": 234.56
  },
  "assignments": [
    {
      "region_name": "广州市",
      "cluster_id": 0,
      "distance": 0.45
    }
  ],
  "cluster_profiles": [
    {
      "cluster_id": 0,
      "region_count": 30,
      "regions": ["广州市", "深圳市"],
      "centroid_norm": 1.23,
      "intra_cluster_variance": 0.45
    }
  ],
  "from_cache": false
}
```

**Error Responses:**
- `400`: Invalid parameters
- `408`: Request timeout (>30s)
- `500`: Computation error

**Performance:** 1-10 seconds (cached results <100ms)

---

### 10. Clustering K-Scan

**POST** `/api/compute/clustering/scan`

Scan multiple k values to find optimal cluster count.

**Request Body:**

```json
{
  "region_level": "county",
  "algorithm": "kmeans",
  "k_range": [2, 3, 4, 5, 6],
  "features": {
    "use_semantic": true,
    "use_morphology": true,
    "use_diversity": true
  },
  "preprocessing": {
    "standardize": true,
    "use_pca": false
  },
  "metric": "silhouette",
  "random_state": 42
}
```

**Response:** `ClusteringScanResult`

```json
{
  "scan_id": "scan_1708416000",
  "results": [
    {
      "k": 2,
      "silhouette_score": 0.56,
      "davies_bouldin_index": 1.23
    },
    {
      "k": 4,
      "silhouette_score": 0.64,
      "davies_bouldin_index": 0.87
    }
  ],
  "best_k": 4,
  "best_score": 0.64,
  "total_time_ms": 5678,
  "from_cache": false
}
```

**Error Responses:**
- `400`: Invalid k_range
- `408`: Request timeout

**Performance:** 5-30 seconds

---

### 11. Semantic Co-occurrence

**POST** `/api/compute/semantic/cooccurrence`

Analyze semantic category co-occurrence patterns.

**Request Body:**

```json
{
  "region_name": null,
  "categories": null,
  "min_cooccurrence": 10,
  "alpha": 0.05
}
```

**Response:** `CooccurrenceResult`

```json
{
  "analysis_id": "cooccur_1708416000",
  "region_name": "all",
  "execution_time_ms": 234,
  "cooccurrence_matrix": [
    {
      "cat1": "water",
      "cat2": "settlement",
      "cooccurrence_count": 1234,
      "pmi": 2.34,
      "chi2_statistic": 567.89,
      "p_value": 0.001
    }
  ],
  "significant_pairs": [
    {
      "cat1": "water",
      "cat2": "settlement",
      "cooccurrence_count": 1234,
      "pmi": 2.34,
      "p_value": 0.001
    }
  ],
  "from_cache": false
}
```

**Performance:** 200-1000ms

---

### 12. Semantic Network

**POST** `/api/compute/semantic/network`

Build semantic network graph with community detection.

**Request Body:**

```json
{
  "min_edge_weight": 1.0,
  "centrality_metrics": ["degree", "betweenness"]
}
```

**Response:** `SemanticNetworkResult`

```json
{
  "network_id": "network_1708416000",
  "node_count": 9,
  "edge_count": 15,
  "execution_time_ms": 456,
  "nodes": [
    {
      "id": "water",
      "degree": 5,
      "betweenness": 0.23
    }
  ],
  "edges": [
    {
      "source": "water",
      "target": "settlement",
      "weight": 2.34
    }
  ],
  "communities": [
    {
      "id": 0,
      "nodes": ["water", "mountain"],
      "size": 2
    }
  ],
  "from_cache": false
}
```

**Performance:** 500-2000ms

---

### 13. Extract Features

**POST** `/api/compute/features/extract`

Extract features for specific villages.

**Request Body:**

```json
{
  "villages": [
    {"name": "水口村", "city": "广州市"},
    {"name": "新村"}
  ],
  "features": {
    "semantic_tags": true,
    "morphology": true,
    "clustering": true
  }
}
```

**Response:** `FeatureExtractionResult`

```json
{
  "extraction_id": "extract_1708416000",
  "village_count": 2,
  "execution_time_ms": 123,
  "features": [
    {
      "village_name": "水口村",
      "city": "广州市",
      "county": "番禺区",
      "semantic_tags": {
        "sem_water": 1,
        "sem_settlement": 1
      },
      "morphology": {
        "name_length": 3,
        "suffix_1": "村",
        "suffix_2": "口",
        "suffix_3": "水"
      },
      "clustering": {
        "kmeans_cluster_id": 2,
        "dbscan_cluster_id": 0,
        "gmm_cluster_id": 1
      }
    }
  ],
  "from_cache": false
}
```

**Performance:** 100-500ms

---

### 14. Aggregate Features

**POST** `/api/compute/features/aggregate`

Aggregate features by region.

**Request Body:**

```json
{
  "region_level": "county",
  "region_names": ["番禺区", "天河区"],
  "features": {
    "semantic_distribution": true,
    "morphology_freq": true,
    "cluster_distribution": true
  },
  "top_n": 10
}
```

**Response:** `FeatureAggregationResult`

```json
{
  "aggregation_id": "aggregate_1708416000",
  "region_level": "county",
  "region_count": 2,
  "execution_time_ms": 234,
  "aggregates": [
    {
      "region_name": "番禺区",
      "total_villages": 1234,
      "semantic_distribution": {
        "sem_water_pct": 0.23,
        "sem_mountain_pct": 0.15
      },
      "top_suffixes": [
        {"suffix": "村", "count": 890},
        {"suffix": "坊", "count": 123}
      ],
      "top_prefixes": [],
      "cluster_distribution": {
        "0": 234,
        "1": 456
      }
    }
  ],
  "from_cache": false
}
```

**Performance:** 200-1000ms

---

### 15. Subset Clustering

**POST** `/api/compute/subset/cluster`

Cluster a subset of villages matching criteria.

**Request Body:**

```json
{
  "filter": {
    "keyword": "水",
    "city": "广州市",
    "county": null
  },
  "algorithm": "kmeans",
  "k": 3,
  "sample_size": 1000,
  "random_state": 42
}
```

**Response:** `SubsetClusteringResult`

```json
{
  "subset_id": "subset_1708416000",
  "matched_villages": 2345,
  "sampled_villages": 1000,
  "execution_time_ms": 1234,
  "clusters": [
    {
      "cluster_id": 0,
      "size": 345,
      "top_semantic_tags": ["water", "settlement"],
      "representative_villages": ["水口村", "水边村"]
    }
  ],
  "metrics": {
    "silhouette_score": 0.56
  },
  "from_cache": false
}
```

**Performance:** 1-5 seconds

---

### 16. Subset Comparison

**POST** `/api/compute/subset/compare`

Compare two groups of villages.

**Request Body:**

```json
{
  "group_a": {
    "keyword": "水",
    "city": null
  },
  "group_b": {
    "keyword": "山",
    "city": null
  },
  "sample_size": 1000,
  "alpha": 0.05
}
```

**Response:** `SubsetComparisonResult`

```json
{
  "comparison_id": "compare_1708416000",
  "group_a_size": 1000,
  "group_b_size": 1000,
  "execution_time_ms": 567,
  "semantic_comparison": [
    {
      "category": "water",
      "group_a_pct": 0.89,
      "group_b_pct": 0.12,
      "difference": 0.77
    }
  ],
  "morphology_comparison": [
    {
      "feature": "avg_name_length",
      "group_a_mean": 3.2,
      "group_b_mean": 3.5,
      "difference": -0.3
    }
  ],
  "significant_differences": [
    {
      "feature": "sem_water_pct",
      "p_value": 0.001,
      "effect_size": 0.89
    }
  ],
  "from_cache": false
}
```

**Performance:** 500-2000ms

---

### 17. Cache Statistics

**GET** `/api/compute/cache/stats`

Get cache performance statistics.

**Query Parameters:** None

**Response:** `CacheStats`

```json
{
  "cache_size": 15,
  "max_size": 100,
  "hit_count": 234,
  "miss_count": 56,
  "hit_rate": 0.81,
  "ttl_seconds": 300
}
```

**Performance:** <10ms

---

### 18. Clear Cache

**POST** `/api/compute/cache/clear`

Clear all cached computation results.

**Request Body:** None

**Response:**

```json
{
  "message": "Cache cleared successfully",
  "cleared_entries": 15
}
```

**Performance:** <10ms

---

## Data Models

### Common Enums

**RegionLevel:**
- `city` - City level (市级)
- `county` - County level (区县级)
- `township` - Township level (乡镇级)

**ClusteringAlgorithm:**
- `kmeans` - K-Means clustering
- `dbscan` - DBSCAN density-based clustering
- `gmm` - Gaussian Mixture Model

**SortBy:**
- `z_score` - Z-score (standardized tendency)
- `lift` - Lift value (relative frequency ratio)
- `log_odds` - Log-odds ratio

### Response Models

All response models are defined using Pydantic. See `/docs` (Swagger UI) for interactive schema documentation.

**Key Models:**
- `CharFrequency` - Character frequency data
- `CharTendency` - Character tendency metrics
- `VillageBasic` - Basic village information
- `VillageDetail` - Detailed village information with features
- `ClusteringResult` - Clustering analysis result
- `SemanticNetworkResult` - Semantic network graph
- `FeatureExtractionResult` - Extracted features
- `SystemOverview` - System statistics

---

## Error Responses

All endpoints return errors in the following format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

### HTTP Status Codes

| Code | Meaning | Common Causes |
|------|---------|---------------|
| `400` | Bad Request | Invalid parameters, missing required fields |
| `404` | Not Found | Resource not found (village, run_id, region) |
| `408` | Request Timeout | Computation exceeded 30-second timeout |
| `422` | Validation Error | Invalid parameter types or values |
| `500` | Internal Server Error | Database error, computation failure |

### Timeout Handling

Online compute endpoints have a 30-second timeout. If computation exceeds this:

```json
{
  "detail": "Request timeout: computation exceeded 30 seconds"
}
```

**Mitigation strategies:**
- Use smaller `sample_size` for subset operations
- Reduce `k_range` for clustering scans
- Filter regions with `region_filter`
- Check cache first (results are cached for 5 minutes)

---

## Common Patterns

### Pagination

Endpoints that return lists support pagination:

```
GET /api/village/search?query=水&limit=20&offset=0
```

- `limit`: Number of results per page (default: 20, max: 100)
- `offset`: Number of results to skip (default: 0)

### Filtering

Most endpoints support region-level filtering:

```
GET /api/character/frequency/regional?region_level=county&region_name=番禺区
```

### Sorting

Tendency endpoints support custom sorting:

```
GET /api/character/tendency/by-region?region_name=广州市&sort_by=z_score
```

### Run ID Versioning

Precomputed endpoints support multiple analysis versions:

```
GET /api/character/frequency/global?run_id=default
GET /api/character/frequency/global?run_id=2024-02-20
```

### Caching

Online compute endpoints cache results for 5 minutes (300 seconds):
- Cache key includes all request parameters
- `from_cache: true` indicates cached result
- Use `/api/compute/cache/clear` to invalidate cache

### CORS

API allows all origins by default (`allow_origins=["*"]`). For production:

```python
# api/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # Restrict to your domain
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

---

## See Also

- [Frontend Integration Guide](FRONTEND_INTEGRATION_GUIDE.md) - Vue 3 integration examples
- [API Deployment Guide](API_DEPLOYMENT_GUIDE.md) - How to deploy the API
- [API Quick Reference](API_QUICK_REFERENCE.md) - One-page cheat sheet
- [Swagger UI](http://localhost:8000/docs) - Interactive API documentation
