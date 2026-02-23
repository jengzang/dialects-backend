# API Quick Reference

One-page cheat sheet for the Guangdong Province Natural Village Analysis API.

---

## Base Information

**Base URL:** `http://localhost:8000`
**Documentation:** `http://localhost:8000/docs` (Swagger UI)
**Health Check:** `GET /health`

---

## Quick Start

```bash
# Start API server
cd api
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Test health
curl http://localhost:8000/health
```

---

## Common Endpoints

### Precomputed (Fast, <100ms)

```bash
# Global character frequency (top 20)
GET /api/character/frequency/global?top_n=20

# Regional character frequency
GET /api/character/frequency/regional?region_level=city&region_name=广州市&top_n=50

# Character tendency by region
GET /api/character/tendency/by-region?region_level=county&region_name=番禺区&top_n=50

# Character tendency by character
GET /api/character/tendency/by-char?character=水&region_level=city

# Search villages
GET /api/village/search?query=水&limit=10&offset=0

# Village detail
GET /api/village/search/detail?village_name=水口村&city=广州市&county=番禺区

# System overview
GET /api/metadata/stats/overview

# Database tables
GET /api/metadata/stats/tables
```

### Online Compute (Slow, 1-30s)

```bash
# Run clustering
POST /api/compute/clustering/run
Body: {
  "region_level": "county",
  "algorithm": "kmeans",
  "k": 4,
  "features": {"use_semantic": true, "use_morphology": true},
  "preprocessing": {"standardize": true}
}

# Clustering k-scan
POST /api/compute/clustering/scan
Body: {
  "region_level": "county",
  "algorithm": "kmeans",
  "k_range": [2, 3, 4, 5],
  "features": {"use_semantic": true}
}

# Semantic co-occurrence
POST /api/compute/semantic/cooccurrence
Body: {
  "min_cooccurrence": 10,
  "alpha": 0.05
}

# Semantic network
POST /api/compute/semantic/network
Body: {
  "min_edge_weight": 1.0,
  "centrality_metrics": ["degree", "betweenness"]
}

# Extract features
POST /api/compute/features/extract
Body: {
  "villages": [{"name": "水口村", "city": "广州市"}],
  "features": {"semantic_tags": true, "morphology": true}
}

# Aggregate features
POST /api/compute/features/aggregate
Body: {
  "region_level": "county",
  "region_names": ["番禺区"],
  "features": {"semantic_distribution": true}
}

# Subset clustering
POST /api/compute/subset/cluster
Body: {
  "filter": {"keyword": "水", "city": "广州市"},
  "algorithm": "kmeans",
  "k": 3,
  "sample_size": 1000
}

# Subset comparison
POST /api/compute/subset/compare
Body: {
  "group_a": {"keyword": "水"},
  "group_b": {"keyword": "山"},
  "sample_size": 1000
}

# Cache stats
GET /api/compute/cache/stats

# Clear cache
POST /api/compute/cache/clear
```

---

## Common Query Parameters

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `run_id` | string | Analysis run ID | `default` |
| `region_level` | string | Region level | `city`, `county`, `township` |
| `region_name` | string | Region name | `广州市`, `番禺区` |
| `limit` | integer | Results per page (1-100) | `20` |
| `offset` | integer | Pagination offset | `0` |
| `top_n` | integer | Top N results | `50` |
| `sort_by` | string | Sort field | `z_score`, `lift`, `log_odds` |

---

## Response Format

### Success Response

```json
{
  "data": [...],
  "metadata": {
    "total": 100,
    "limit": 20,
    "offset": 0
  }
}
```

Or direct array:

```json
[
  {"character": "村", "frequency": 125430},
  {"character": "新", "frequency": 45678}
]
```

### Error Response

```json
{
  "detail": "Error message"
}
```

---

## HTTP Status Codes

| Code | Meaning | Action |
|------|---------|--------|
| `200` | Success | Process response |
| `400` | Bad Request | Check parameters |
| `404` | Not Found | Resource doesn't exist |
| `408` | Timeout | Reduce data size or retry |
| `422` | Validation Error | Fix parameter types/values |
| `500` | Server Error | Check logs, contact admin |

---

## JavaScript Examples

### Fetch API

```javascript
// GET request
const response = await fetch('http://localhost:8000/api/village/search?query=水&limit=10');
const villages = await response.json();

// POST request
const response = await fetch('http://localhost:8000/api/compute/clustering/run', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    region_level: 'county',
    algorithm: 'kmeans',
    k: 4,
    features: { use_semantic: true },
    preprocessing: { standardize: true }
  })
});
const result = await response.json();
```

### Axios

```javascript
import axios from 'axios';

// GET request
const { data } = await axios.get('http://localhost:8000/api/village/search', {
  params: { query: '水', limit: 10 }
});

// POST request
const { data } = await axios.post('http://localhost:8000/api/compute/clustering/run', {
  region_level: 'county',
  algorithm: 'kmeans',
  k: 4,
  features: { use_semantic: true },
  preprocessing: { standardize: true }
});
```

---

## Vue 3 Composable

```javascript
// useVillageSearch.js
import { ref } from 'vue';

export function useVillageSearch() {
  const villages = ref([]);
  const loading = ref(false);
  const error = ref(null);

  async function search(keyword) {
    loading.value = true;
    error.value = null;

    try {
      const response = await fetch(
        `http://localhost:8000/api/village/search?query=${keyword}&limit=10`
      );
      villages.value = await response.json();
    } catch (err) {
      error.value = err.message;
    } finally {
      loading.value = false;
    }
  }

  return { villages, loading, error, search };
}
```

---

## Common Patterns

### Pagination

```javascript
function loadPage(page, pageSize = 20) {
  const offset = (page - 1) * pageSize;
  return fetch(`/api/village/search?query=水&limit=${pageSize}&offset=${offset}`);
}
```

### Debounced Search

```javascript
import { debounce } from 'lodash-es';

const debouncedSearch = debounce(async (keyword) => {
  const response = await fetch(`/api/village/search?query=${keyword}`);
  const results = await response.json();
  // Update UI
}, 300);
```

### Error Handling

```javascript
async function safeApiCall(url) {
  try {
    const response = await fetch(url);
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail);
    }
    return response.json();
  } catch (err) {
    console.error('API Error:', err.message);
    return null;
  }
}
```

### Timeout Handling

```javascript
async function fetchWithTimeout(url, timeout = 30000) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const response = await fetch(url, { signal: controller.signal });
    clearTimeout(timeoutId);
    return response.json();
  } catch (err) {
    if (err.name === 'AbortError') {
      throw new Error('Request timeout');
    }
    throw err;
  }
}
```

---

## Configuration

### Environment Variables

```bash
# .env
VILLAGES_DB_PATH=/path/to/villages.db
API_TITLE="Village Analysis API"
DEFAULT_PAGE_SIZE=20
MAX_PAGE_SIZE=100
COMPUTE_TIMEOUT=30
CACHE_TTL=300
ALLOWED_ORIGINS=https://yourdomain.com
LOG_LEVEL=info
```

### CORS (Production)

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

## Performance Tips

1. **Use pagination** - Don't load all results at once
2. **Debounce search** - Wait 300ms before API call
3. **Cache results** - API caches compute results for 5 minutes
4. **Check cache first** - `from_cache: true` in response
5. **Reduce sample_size** - For subset operations, use 1000 instead of 10000
6. **Use smaller k_range** - For clustering scans, use [2,3,4,5] instead of [2..10]
7. **Filter regions** - Use `region_filter` to reduce computation

---

## Troubleshooting

### Database Not Found

```bash
# Check database path
ls -l data/villages.db

# Update path in api/dependencies.py
DB_PATH = "/absolute/path/to/villages.db"
```

### CORS Error

```python
# Add your frontend origin to api/main.py
allow_origins=["http://localhost:5173"]  # Vite default port
```

### Timeout (408)

- Reduce `sample_size` parameter
- Use smaller `k_range` for scans
- Check if results are cached
- Increase timeout in `api/compute/timeout.py`

### Import Error

```bash
# Run from project root
python -m uvicorn api.main:app

# Or set PYTHONPATH
export PYTHONPATH=/path/to/villages-ML:$PYTHONPATH
```

---

## Deployment

### Docker

```bash
# Build image
docker build -t village-api .

# Run container
docker run -d -p 8000:8000 \
  -v $(pwd)/data/villages.db:/app/data/villages.db:ro \
  village-api
```

### Systemd Service

```bash
# Create service file
sudo nano /etc/systemd/system/village-api.service

# Enable and start
sudo systemctl enable village-api
sudo systemctl start village-api
```

### Nginx Reverse Proxy

```nginx
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_read_timeout 60s;
}
```

---

## Resources

- **API Reference:** [API_REFERENCE.md](API_REFERENCE.md)
- **Frontend Guide:** [FRONTEND_INTEGRATION_GUIDE.md](FRONTEND_INTEGRATION_GUIDE.md)
- **Deployment Guide:** [API_DEPLOYMENT_GUIDE.md](API_DEPLOYMENT_GUIDE.md)
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

---

## Support

- **Issues:** Check logs at `/var/log/village-api/api.log`
- **Health Check:** `curl http://localhost:8000/health`
- **Cache Stats:** `GET /api/compute/cache/stats`
- **Clear Cache:** `POST /api/compute/cache/clear`