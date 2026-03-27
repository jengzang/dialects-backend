# Analytics API Quick Start Guide

## Installation

1. **Install dependencies**:
```bash
pip install geoip2 user-agents openpyxl
```

2. **Verify GeoLite2 databases exist**:
```bash
ls data/dependency/GeoLite2-*.mmdb
```

Expected files:
- `GeoLite2-City.mmdb`
- `GeoLite2-Country.mmdb`
- `GeoLite2-ASN.mmdb`

## Quick Test

### 1. Start the server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 5000
```

### 2. Login as admin

```bash
curl -X POST "http://localhost:5000/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=your_password"
```

Save the `access_token` from the response.

### 3. Test the dashboard endpoint

```bash
curl -X GET "http://localhost:5000/admin/analytics/dashboard" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## Common Use Cases

### 1. Get System Overview

```bash
GET /admin/analytics/dashboard
```

Returns:
- Total users and active users
- Total API calls and traffic
- Top 10 APIs
- User distribution by activity level
- Monthly new users trend

### 2. Identify High-Value Users

```bash
GET /admin/analytics/rfm-analysis?include_users=true
```

Returns users segmented by RFM scores:
- VIP users (high recency, frequency, monetary)
- Potential users
- Dormant high-value users (need re-engagement)

### 3. Detect Anomalies

```bash
GET /admin/analytics/anomaly-detection?detection_type=all
```

Detects:
- Users with abnormally high API usage
- Users with abnormally high traffic
- Users dependent on single API
- New users with suspicious activity

### 4. Analyze API Performance

```bash
GET /admin/analytics/api-performance
```

Returns:
- Average response time per API
- P50/P95/P99 percentiles
- Slow request ratios
- Performance trends

### 5. Export Data

```bash
# Export as Excel
GET /admin/analytics/export?export_type=user-segments&format=xlsx

# Export as CSV
GET /admin/analytics/export?export_type=rfm&format=csv

# Export as JSON
GET /admin/analytics/export?export_type=dashboard&format=json
```

## Python Example

```python
import requests

# Configuration
BASE_URL = "http://localhost:5000"
USERNAME = "admin"
PASSWORD = "your_password"

# Login
response = requests.post(
    f"{BASE_URL}/auth/login",
    data={"username": USERNAME, "password": PASSWORD}
)
token = response.json()["access_token"]

# Get dashboard data
headers = {"Authorization": f"Bearer {token}"}
response = requests.get(
    f"{BASE_URL}/admin/analytics/dashboard",
    headers=headers
)
dashboard = response.json()

print(f"Total Users: {dashboard['overview']['total_users']}")
print(f"Active Users (7d): {dashboard['overview']['active_users_7d']}")
print(f"Total API Calls: {dashboard['overview']['total_calls']}")
```

## JavaScript Example

```javascript
// Login
const loginResponse = await fetch('http://localhost:5000/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  body: 'username=admin&password=your_password'
});
const { access_token } = await loginResponse.json();

// Get dashboard
const dashboardResponse = await fetch('http://localhost:5000/admin/analytics/dashboard', {
  headers: { 'Authorization': `Bearer ${access_token}` }
});
const dashboard = await dashboardResponse.json();

console.log('Total Users:', dashboard.overview.total_users);
console.log('Active Users (7d):', dashboard.overview.active_users_7d);
```

## Available Endpoints

| Endpoint | Description | Key Parameters |
|----------|-------------|----------------|
| `/user-segments` | User activity segmentation | `include_users` |
| `/rfm-analysis` | RFM value analysis | `include_users` |
| `/anomaly-detection` | Anomaly detection | `detection_type` |
| `/api-diversity` | API diversity analysis | `sort_by` |
| `/user-preferences` | User preferences | `user_ids` |
| `/user-growth` | User growth statistics | `months` |
| `/dashboard` | System overview | - |
| `/recent-trends` | Recent trends (7 days) | `granularity`, `days` |
| `/api-performance` | API performance metrics | `api_path` |
| `/geo-distribution` | Geographic distribution | `level` |
| `/device-distribution` | Device distribution | - |
| `/export` | Data export | `export_type`, `format` |

## Troubleshooting

### Issue: "GeoLite2 database not found"

**Solution**: Download GeoLite2 databases from MaxMind and place them in `data/dependency/`:
```bash
# Download from https://dev.maxmind.com/geoip/geolite2-free-geolocation-data
# Or use existing files if available
```

### Issue: "401 Unauthorized"

**Solution**: Ensure you're using a valid admin access token:
```bash
# Re-login to get a fresh token
curl -X POST "http://localhost:5000/auth/login" \
  -d "username=admin&password=your_password"
```

### Issue: "Empty data returned"

**Solution**: Ensure you have:
1. Users in the database
2. API usage data in `api_usage_summary` table
3. Recent logs in `api_usage_logs` table (for trends/performance/geo/devices)

### Issue: "Slow response times"

**Solution**:
1. Add database indexes (see documentation)
2. Implement Redis caching for expensive queries
3. Use `include_users=false` to reduce response size

## Performance Tips

1. **Use caching**: Implement Redis caching for dashboard and segments (1 hour TTL)
2. **Limit user details**: Use `include_users=false` for faster responses
3. **Export large datasets**: Use export endpoint instead of fetching all data via API
4. **Monitor database**: Ensure indexes are created and database is optimized

## Next Steps

1. Read the full documentation: `docs/admin_analytics_api.md`
2. Explore the implementation plan: `docs/admin_analytics_implementation.md`
3. Test all endpoints using: `test_analytics_api.py`
4. Integrate with your frontend dashboard

## Support

For issues or questions:
- Check `CLAUDE.md` for project guidelines
- Review `docs/` for detailed documentation
- Report issues on GitHub
