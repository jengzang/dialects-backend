# Admin Leaderboard API Reference

## Overview

The admin leaderboard API provides comprehensive ranking views across multiple dimensions:
- **User global rankings**: Aggregated statistics across all APIs
- **User by API rankings**: Per-API user performance
- **API endpoint rankings**: Which APIs are most popular
- **Online time rankings**: User activity duration

## Authentication

All endpoints require admin authentication:
```
Authorization: Bearer <admin_access_token>
```

## Endpoints

### 1. Get Rankings

```
GET /admin/leaderboard/rankings
```

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| ranking_type | string | Yes | Type of ranking: `user_global`, `user_by_api`, `api`, `online_time` |
| metric | string | Conditional | Metric: `count`, `duration`, `upload`, `download` (not needed for `online_time`) |
| api_path | string | Conditional | API path (required for `user_by_api` type) |
| page | integer | No | Page number (default: 1) |
| page_size | integer | No | Items per page (default: 20, max: 100) |

**Response:**

```json
{
  "ranking_type": "user_global",
  "metric": "count",
  "api_path": null,
  "total_count": 150,
  "page": 1,
  "page_size": 20,
  "total_pages": 8,
  "rankings": [
    {
      "rank": 1,
      "user_id": 5,
      "username": "user123",
      "value": 5000.0,
      "percentage": 100.0,
      "gap_to_prev": null,
      "first_place_value": 5000.0
    },
    {
      "rank": 2,
      "user_id": 3,
      "username": "user456",
      "value": 4500.0,
      "percentage": 90.0,
      "gap_to_prev": 500.0,
      "first_place_value": 5000.0
    }
  ]
}
```

### 2. Get Available APIs

```
GET /admin/leaderboard/available-apis
```

Returns a list of all API paths that have usage records.

**Response:**

```json
{
  "apis": [
    "/api/YinWei",
    "/api/ZhongGu",
    "/api/search_chars/",
    ...
  ]
}
```

## Usage Examples

### Example 1: User Global Ranking by Call Count

```bash
curl -X GET "http://localhost:5000/admin/leaderboard/rankings?ranking_type=user_global&metric=count&page=1&page_size=20" \
  -H "Authorization: Bearer <token>"
```

### Example 2: User Ranking for Specific API

```bash
curl -X GET "http://localhost:5000/admin/leaderboard/rankings?ranking_type=user_by_api&metric=duration&api_path=/api/YinWei&page=1" \
  -H "Authorization: Bearer <token>"
```

### Example 3: API Endpoint Ranking by Download Traffic

```bash
curl -X GET "http://localhost:5000/admin/leaderboard/rankings?ranking_type=api&metric=download&page=1" \
  -H "Authorization: Bearer <token>"
```

### Example 4: Online Time Ranking

```bash
curl -X GET "http://localhost:5000/admin/leaderboard/rankings?ranking_type=online_time&page=1" \
  -H "Authorization: Bearer <token>"
```

### Example 5: Get Available APIs

```bash
curl -X GET "http://localhost:5000/admin/leaderboard/available-apis" \
  -H "Authorization: Bearer <token>"
```

## Ranking Types Matrix

| Ranking Type | Metrics Available | Additional Parameters | Description |
|--------------|-------------------|----------------------|-------------|
| `user_global` | count, duration, upload, download | - | Users ranked by aggregated stats across all APIs |
| `user_by_api` | count, duration, upload, download | api_path (required) | Users ranked by stats for a specific API |
| `api` | count, duration, upload, download | - | APIs ranked by total usage |
| `online_time` | - | - | Users ranked by total online time |

## Response Fields

### User Ranking Item

| Field | Type | Description |
|-------|------|-------------|
| rank | integer | User's rank (1 = first place) |
| user_id | integer | User ID |
| username | string | Username |
| value | float | Metric value |
| percentage | float | Percentage of first place value |
| gap_to_prev | float/null | Gap to previous rank (null for rank 1) |
| first_place_value | float | First place value for reference |

### API Ranking Item

| Field | Type | Description |
|-------|------|-------------|
| rank | integer | API's rank |
| path | string | API path |
| value | float | Metric value |
| percentage | float | Percentage of first place value |
| unique_users | integer | Number of unique users |
| gap_to_prev | float/null | Gap to previous rank |
| first_place_value | float | First place value |

## Error Responses

### 400 Bad Request

```json
{
  "detail": "online_time类型不需要metric参数"
}
```

Common validation errors:
- `online_time` type with `metric` parameter
- `user_by_api` type without `api_path` parameter
- `user_global`/`api` type without `metric` parameter

### 401 Unauthorized

```json
{
  "detail": "Not authenticated"
}
```

### 403 Forbidden

```json
{
  "detail": "Admin access required"
}
```

## Testing

Run the test suite:

```bash
python test_admin_leaderboard.py
```

Make sure to update the admin credentials in the test file before running.

## Performance Notes

- All queries use database indexes on `user_id` and `path`
- Pagination is recommended for large datasets
- Consider adding caching (5-10 minutes) for frequently accessed rankings
- Rankings are calculated in real-time from the `api_usage_summary` table
