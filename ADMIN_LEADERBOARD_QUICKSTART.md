# Admin Leaderboard - Quick Start Guide

## What Was Implemented

A comprehensive admin leaderboard system with 4 ranking types and multiple metrics, providing 89+ possible ranking combinations.

## Files Modified/Created

### Created:
- `app/admin/__init__.py`
- `app/admin/leaderboard_service.py` - Core ranking logic
- `app/routes/admin/leaderboard.py` - API endpoints
- `test_admin_leaderboard.py` - Test suite
- `docs/admin_leaderboard_api.md` - API reference
- `docs/admin_leaderboard_implementation.md` - Implementation details

### Modified:
- `app/schemas/admin.py` - Added leaderboard schemas
- `app/routes/admin/__init__.py` - Registered leaderboard routes

## Quick Test

### 1. Start the Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 5000
```

### 2. Get Admin Token

```bash
curl -X POST "http://localhost:5000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your_password"}'
```

Save the `access_token` from the response.

### 3. Test Rankings

#### Get User Global Ranking (by call count)
```bash
curl -X GET "http://localhost:5000/admin/leaderboard/rankings?ranking_type=user_global&metric=count&page=1&page_size=10" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Get Available APIs
```bash
curl -X GET "http://localhost:5000/admin/leaderboard/available-apis" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Get API Endpoint Ranking
```bash
curl -X GET "http://localhost:5000/admin/leaderboard/rankings?ranking_type=api&metric=count&page=1" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Get Online Time Ranking
```bash
curl -X GET "http://localhost:5000/admin/leaderboard/rankings?ranking_type=online_time&page=1" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 4. Run Full Test Suite

```bash
# Update credentials in test file first
python test_admin_leaderboard.py
```

## API Endpoints

### Main Endpoint
```
GET /admin/leaderboard/rankings
```

**Parameters:**
- `ranking_type` (required): user_global | user_by_api | api | online_time
- `metric` (conditional): count | duration | upload | download
- `api_path` (conditional): API path for user_by_api type
- `page` (optional): Page number (default: 1)
- `page_size` (optional): Items per page (default: 20, max: 100)

### Helper Endpoint
```
GET /admin/leaderboard/available-apis
```

## Ranking Types

| Type | Description | Metrics | Extra Params |
|------|-------------|---------|--------------|
| user_global | Users ranked by total stats | count, duration, upload, download | - |
| user_by_api | Users ranked by specific API | count, duration, upload, download | api_path |
| api | APIs ranked by usage | count, duration, upload, download | - |
| online_time | Users ranked by online time | - | - |

## Response Example

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
    }
  ]
}
```

## Swagger Documentation

Access interactive API docs at:
```
http://localhost:5000/docs#/admin%20leaderboard
```

## Common Use Cases

### 1. Find Top 10 Most Active Users
```
GET /admin/leaderboard/rankings?ranking_type=user_global&metric=count&page=1&page_size=10
```

### 2. See Which APIs Are Most Popular
```
GET /admin/leaderboard/rankings?ranking_type=api&metric=count&page=1&page_size=20
```

### 3. Find Top Users for Specific API
```
GET /admin/leaderboard/rankings?ranking_type=user_by_api&metric=count&api_path=/api/YinWei&page=1
```

### 4. See Who Spends Most Time Online
```
GET /admin/leaderboard/rankings?ranking_type=online_time&page=1&page_size=10
```

## Troubleshooting

### Import Errors
If you see import errors, make sure all files are in the correct locations:
```bash
ls app/admin/leaderboard_service.py
ls app/routes/admin/leaderboard.py
```

### Permission Denied
Make sure you're using an admin account token. Regular users cannot access these endpoints.

### Empty Rankings
If rankings are empty, check if there's data in the `api_usage_summary` table:
```sql
SELECT COUNT(*) FROM api_usage_summary;
```

## Next Steps

1. ✅ Implementation complete
2. ⏳ Test with your admin account
3. ⏳ Integrate with frontend
4. ⏳ Consider adding caching for performance
5. ⏳ Optional: Add time range filtering

## Documentation

- Full API Reference: `docs/admin_leaderboard_api.md`
- Implementation Details: `docs/admin_leaderboard_implementation.md`
- Test Suite: `test_admin_leaderboard.py`
