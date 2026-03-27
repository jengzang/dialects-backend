# User Behavior Analytics API Documentation

## Overview

The User Behavior Analytics system provides comprehensive insights into user activity, API usage patterns, and system performance. All endpoints require admin authentication.

**Base URL**: `/admin/analytics`

## Authentication

All endpoints require admin authentication via JWT token:

```bash
Authorization: Bearer <admin_access_token>
```

## Endpoints

### 1. User Activity Segmentation

**Endpoint**: `GET /admin/analytics/user-segments`

**Description**: Segments users by activity level based on total API calls and recency.

**Query Parameters**:
- `include_users` (boolean, optional): Include detailed user list. Default: `false`

**Segmentation Criteria**:
- **Super Active**: total_calls > 1000 AND active within 7 days
- **Active**: total_calls > 500 AND active within 14 days
- **Regular**: total_calls > 100 AND active within 30 days
- **Low Active**: total_calls > 10 AND active within 60 days
- **Dormant**: inactive for 60+ days

**Example Request**:
```bash
curl -X GET "http://localhost:5000/admin/analytics/user-segments?include_users=false" \
  -H "Authorization: Bearer <token>"
```

**Example Response**:
```json
{
  "segments": [
    {
      "level": "super_active",
      "count": 12,
      "percentage": 8.0,
      "avg_calls": 1500,
      "avg_duration": 5000.25
    }
  ],
  "total_users": 150
}
```

---

### 2. RFM User Value Analysis

**Endpoint**: `GET /admin/analytics/rfm-analysis`

**Description**: Analyzes user value using RFM (Recency, Frequency, Monetary) model.

**Query Parameters**:
- `include_users` (boolean, optional): Include detailed user list. Default: `false`

**RFM Metrics**:
- **R (Recency)**: Days since last activity (lower is better)
- **F (Frequency)**: Total API calls (higher is better)
- **M (Monetary)**: total_duration + (total_upload + total_download) / 1000

**User Segments**:
- **VIP**: R>=4, F>=4, M>=4
- **Potential**: R>=4, F>=3, M>=3
- **New**: R>=4, F<=2, M<=2
- **Dormant High Value**: R<=2, F>=4, M>=4
- **Low Value**: R<=2, F<=2, M<=2
- **Others**: Everything else

**Example Response**:
```json
{
  "segments": [
    {
      "segment": "VIP",
      "count": 15,
      "avg_recency_days": 2.5,
      "avg_frequency": 1200,
      "avg_monetary": 8000.50
    }
  ]
}
```

---

### 3. Anomaly Detection

**Endpoint**: `GET /admin/analytics/anomaly-detection`

**Description**: Detects anomalous user behavior patterns.

**Query Parameters**:
- `detection_type` (string, optional): Type of anomaly to detect. Default: `all`
  - `all`: All detection types
  - `high_frequency`: Users with calls > mean + 3*std
  - `high_traffic`: Users with traffic > mean + 3*std
  - `single_api`: Users with 90%+ calls on single API
  - `new_user_spike`: Users registered < 7 days with > 100 calls

**Example Response**:
```json
{
  "anomalies": [
    {
      "type": "high_frequency",
      "user_id": 12,
      "username": "user456",
      "value": 5000,
      "avg_value": 150.25,
      "z_score": 24.25,
      "severity": "high"
    }
  ]
}
```

---

### 4. API Diversity Analysis

**Endpoint**: `GET /admin/analytics/api-diversity`

**Description**: Analyzes how diverse users' API usage patterns are.

**Query Parameters**:
- `sort_by` (string, optional): Sort by `diversity` or `calls`. Default: `diversity`

**Metrics**:
- **API Count**: Number of different APIs used
- **Diversity Score**: api_count / total_calls
- **User Type**:
  - 探索型 (Explorer): diversity > 0.01
  - 专注型 (Focused): diversity <= 0.01

**Example Response**:
```json
{
  "users": [
    {
      "user_id": 5,
      "username": "user123",
      "api_count": 8,
      "total_calls": 1500,
      "diversity_score": 0.0053,
      "user_type": "探索型"
    }
  ],
  "summary": {
    "total_users": 150,
    "avg_diversity": 0.0035,
    "explorer_count": 45,
    "focused_count": 105
  }
}
```

---

### 5. User Preferences Analysis

**Endpoint**: `GET /admin/analytics/user-preferences`

**Description**: Analyzes user preferences based on API usage patterns. Returns detailed data for frontend to generate labels.

**Query Parameters**:
- `user_ids` (string, optional): Comma-separated user IDs to analyze

**API Categories**:
- 音韵查询 (Phonological Query)
- 字调查询 (Character/Tone Query)
- 音系分析 (Phonological Analysis)
- 工具使用 (Tool Usage)
- 其他 (Others)

**Example Response**:
```json
{
  "users": [
    {
      "user_id": 5,
      "username": "user123",
      "category_distribution": {
        "音韵查询": 60.0,
        "字调查询": 25.0,
        "音系分析": 10.0,
        "工具使用": 5.0
      },
      "total_calls": 1500,
      "api_diversity": 8,
      "diversity_score": 0.0053,
      "traffic_pattern": {
        "upload_ratio": 0.3,
        "download_ratio": 0.7,
        "total_traffic_kb": 5000.25
      },
      "top_apis": [
        {
          "path": "/api/YinWei",
          "calls": 600,
          "percentage": 40.0
        }
      ]
    }
  ]
}
```

---

### 6. User Growth Statistics

**Endpoint**: `GET /admin/analytics/user-growth`

**Description**: Analyzes user growth trends over time.

**Query Parameters**:
- `months` (integer, optional): Number of recent months to analyze. Default: `12`

**Example Response**:
```json
{
  "monthly_growth": [
    {
      "month": "2026-01",
      "new_users": 45,
      "cumulative_users": 150,
      "growth_rate": 15.0
    },
    {
      "month": "2026-02",
      "new_users": 50,
      "cumulative_users": 200,
      "growth_rate": 11.1
    }
  ],
  "summary": {
    "total_users": 200,
    "avg_monthly_growth": 13.0,
    "months_analyzed": 12
  }
}
```

---

### 7. System Overview Dashboard

**Endpoint**: `GET /admin/analytics/dashboard`

**Description**: Provides comprehensive system statistics.

**Example Response**:
```json
{
  "overview": {
    "total_users": 200,
    "active_users_7d": 85,
    "active_users_30d": 150,
    "total_calls": 50000,
    "total_traffic_mb": 1500.25
  },
  "top_apis": [
    {
      "path": "/api/YinWei",
      "calls": 15000,
      "users": 120
    }
  ],
  "user_distribution": {
    "super_active": 12,
    "active": 35,
    "regular": 58,
    "low_active": 30,
    "dormant": 15
  },
  "monthly_new_users": [
    {
      "month": "2026-01",
      "new_users": 45
    }
  ]
}
```

---

### 8. Recent Trends Analysis

**Endpoint**: `GET /admin/analytics/recent-trends`

**Description**: Analyzes API usage trends from recent logs (last 7 days).

**Query Parameters**:
- `granularity` (string, optional): `day` or `hour`. Default: `day`
- `days` (integer, optional): Number of days to analyze (max 7). Default: `7`

**Example Response**:
```json
{
  "period": "7d",
  "granularity": "day",
  "trends": [
    {
      "time": "2026-03-01",
      "total_calls": 1200,
      "active_users": 45,
      "avg_duration": 0.35,
      "top_api": "/api/YinWei"
    }
  ],
  "summary": {
    "total_calls": 8400,
    "avg_daily_calls": 1200.0,
    "peak_time": "2026-03-03",
    "peak_calls": 1500
  }
}
```

---

### 9. API Performance Analysis

**Endpoint**: `GET /admin/analytics/api-performance`

**Description**: Analyzes API response time and performance metrics.

**Query Parameters**:
- `api_path` (string, optional): Specific API path to analyze

**Metrics**:
- **avg_duration**: Average response time (seconds)
- **p50**: 50th percentile (median)
- **p95**: 95th percentile
- **p99**: 99th percentile
- **slow_request_ratio**: Percentage of requests > 1 second

**Example Response**:
```json
{
  "apis": [
    {
      "path": "/api/YinWei",
      "avg_duration": 0.35,
      "p50": 0.25,
      "p95": 0.80,
      "p99": 1.50,
      "slow_request_ratio": 5.2,
      "total_calls": 1500
    }
  ],
  "summary": {
    "overall_avg": 0.42,
    "slowest_api": "/api/phonology_matrix",
    "total_apis": 25
  }
}
```

---

### 10. Geographic Distribution Analysis

**Endpoint**: `GET /admin/analytics/geo-distribution`

**Description**: Analyzes user geographic distribution using GeoLite2 database.

**Query Parameters**:
- `level` (string, optional): `country` or `city`. Default: `country`

**Requirements**:
- GeoLite2 database files must be present in `data/dependency/`

**Example Response**:
```json
{
  "level": "country",
  "distribution": [
    {
      "location": "中国",
      "user_count": 150,
      "call_count": 8000,
      "percentage": 85.0
    },
    {
      "location": "美国",
      "user_count": 20,
      "call_count": 1200,
      "percentage": 10.0
    }
  ],
  "total_locations": 15
}
```

---

### 11. Device Distribution Analysis

**Endpoint**: `GET /admin/analytics/device-distribution`

**Description**: Analyzes user device types, browsers, and operating systems.

**Example Response**:
```json
{
  "device_types": [
    {
      "name": "desktop",
      "count": 120,
      "percentage": 80.0
    },
    {
      "name": "mobile",
      "count": 25,
      "percentage": 16.7
    }
  ],
  "browsers": [
    {
      "name": "Chrome",
      "count": 100,
      "percentage": 66.7
    }
  ],
  "os": [
    {
      "name": "Windows",
      "count": 80,
      "percentage": 53.3
    }
  ],
  "total_users": 150
}
```

---

### 12. Data Export

**Endpoint**: `GET /admin/analytics/export`

**Description**: Exports analytics data in various formats.

**Query Parameters**:
- `export_type` (string, required): Type of data to export
  - `user-segments`, `rfm`, `anomalies`, `diversity`, `preferences`, `growth`, `dashboard`, `trends`, `performance`, `geo`, `devices`
- `format` (string, optional): Export format. Default: `csv`
  - `csv`: Comma-separated values
  - `xlsx`: Excel spreadsheet
  - `json`: JSON format
- `flatten` (boolean, optional): Flatten nested structures for CSV/Excel. Default: `false`
- `include_users` (boolean, optional): Include user details (where applicable). Default: `false`

**Example Request**:
```bash
curl -X GET "http://localhost:5000/admin/analytics/export?export_type=user-segments&format=xlsx" \
  -H "Authorization: Bearer <token>" \
  -o user_segments.xlsx
```

**Response**: File download (CSV, Excel, or JSON)

---

## Data Sources

### api_usage_summary Table
- Cumulative aggregated data
- Used by: Segmentation, RFM, Anomaly, Diversity, Preferences, Growth, Dashboard

### api_usage_logs Table
- Detailed logs (retained for 7 days)
- Used by: Trends, Performance, Geo, Devices

### users Table
- User registration and activity data
- Used by: All analytics modules

---

## Performance Considerations

### Caching
- Dashboard data: 1 hour TTL (recommended)
- User segments: 1 hour TTL (recommended)
- RFM analysis: 1 hour TTL (recommended)
- Recent trends: 10 minutes TTL (recommended)

### Database Indexes
Ensure the following indexes exist for optimal performance:

```sql
CREATE INDEX idx_users_last_seen ON users(last_seen);
CREATE INDEX idx_users_created_at ON users(created_at);
CREATE INDEX idx_api_usage_summary_user_path ON api_usage_summary(user_id, path);
CREATE INDEX idx_api_usage_logs_called_at ON api_usage_logs(called_at);
CREATE INDEX idx_api_usage_logs_user_id ON api_usage_logs(user_id);
```

---

## Error Handling

All endpoints return standard HTTP status codes:

- `200 OK`: Success
- `401 Unauthorized`: Missing or invalid authentication token
- `403 Forbidden`: User is not an admin
- `404 Not Found`: Endpoint not found
- `500 Internal Server Error`: Server error

**Error Response Format**:
```json
{
  "detail": "Error message"
}
```

---

## Dependencies

The analytics system requires the following Python packages:

```
geoip2>=4.7.0
user-agents>=2.2.0
openpyxl>=3.1.5
```

And the following data files:

```
data/dependency/GeoLite2-City.mmdb
data/dependency/GeoLite2-Country.mmdb
```

---

## Implementation Notes

### Module Structure

```
app/admin/analytics/
├── __init__.py           # Module exports
├── segmentation.py       # User activity segmentation
├── rfm.py                # RFM value analysis
├── anomaly.py            # Anomaly detection
├── diversity.py          # API diversity analysis
├── preferences.py        # User preferences
├── growth.py             # User growth statistics
├── dashboard.py          # System overview
├── trends.py             # Recent trends analysis
├── performance.py        # API performance metrics
├── geo.py                # Geographic distribution
├── devices.py            # Device distribution
└── export.py             # Data export utilities
```

### Route Registration

Routes are registered in `app/routes/admin/__init__.py`:

```python
from .analytics import router as analytics_router

router.include_router(
    analytics_router,
    prefix="/analytics",
    tags=["admin analytics"],
    dependencies=[Depends(get_current_admin_user)]
)
```

---

## Testing

Use the provided test script to verify all endpoints:

```bash
python test_analytics_api.py
```

Or test individual endpoints using curl:

```bash
# Login
TOKEN=$(curl -X POST "http://localhost:5000/api/auth/login" \
  -d "username=admin&password=admin" | jq -r '.access_token')

# Test dashboard
curl -X GET "http://localhost:5000/admin/analytics/dashboard" \
  -H "Authorization: Bearer $TOKEN" | jq
```

---

## Future Enhancements

Potential improvements for future versions:

1. **Real-time Analytics**: WebSocket-based real-time updates
2. **Custom Alerts**: Configurable alerts for anomalies
3. **Predictive Analytics**: ML-based user behavior prediction
4. **Cohort Analysis**: User cohort tracking and retention analysis
5. **A/B Testing**: Built-in A/B testing framework
6. **Custom Dashboards**: User-configurable dashboard widgets
7. **Scheduled Reports**: Automated email reports
8. **API Recommendations**: Suggest APIs based on user behavior

---

## Support

For issues or questions, please refer to:
- Project documentation: `docs/`
- CLAUDE.md: Project guidelines
- GitHub issues: https://github.com/anthropics/claude-code/issues
