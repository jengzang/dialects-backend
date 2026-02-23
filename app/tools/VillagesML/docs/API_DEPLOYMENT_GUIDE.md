# API Deployment Guide

Step-by-step guide for deploying the Guangdong Province Natural Village Analysis API.

---

## Table of Contents

1. [Local Development Setup](#local-development-setup)
2. [Integrating into Existing FastAPI Backend](#integrating-into-existing-fastapi-backend)
3. [Production Deployment](#production-deployment)
4. [Configuration](#configuration)
5. [Performance Optimization](#performance-optimization)
6. [Security Considerations](#security-considerations)
7. [Monitoring and Logging](#monitoring-and-logging)

---

## Local Development Setup

### Prerequisites

- Python 3.8+
- pip
- SQLite database at `data/villages.db`

### Installation Steps

1. **Navigate to API directory:**

```bash
cd api
```

2. **Install dependencies:**

```bash
pip install -r requirements.txt
```

3. **Verify database path:**

The API expects the database at `../../data/villages.db` relative to the `api/` directory.

```
villages-ML/
├── api/
│   ├── main.py
│   └── dependencies.py
└── data/
    └── villages.db  # Database should be here
```

4. **Run the development server:**

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

5. **Test the API:**

```bash
curl http://localhost:8000/health
# Expected: {"status": "healthy"}
```

6. **Access Swagger UI:**

Open browser: `http://localhost:8000/docs`

---

## Integrating into Existing FastAPI Backend

### Scenario

You have an existing FastAPI application and want to integrate the village analysis API.

### Option 1: Copy Entire `/api` Directory

**Step 1: Copy files**

```bash
# From your existing FastAPI project root
cp -r /path/to/villages-ML/api ./village_analysis
```

**Step 2: Update database path**

Edit `village_analysis/dependencies.py`:

```python
# Before
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "villages.db")

# After (adjust to your database location)
DB_PATH = "/absolute/path/to/villages.db"
# Or use environment variable
DB_PATH = os.getenv("VILLAGES_DB_PATH", "/path/to/villages.db")
```

**Step 3: Update CORS configuration**

Edit `village_analysis/main.py`:

```python
# Restrict origins for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # Your frontend domain
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

**Step 4: Mount as sub-application**

In your main FastAPI app:

```python
# your_app/main.py
from fastapi import FastAPI
from village_analysis.main import app as village_app

app = FastAPI(title="Your Main App")

# Mount village analysis API
app.mount("/village-api", village_app)

# Your existing routes
@app.get("/")
def root():
    return {"message": "Main app"}
```

Now the village API is available at:
- `http://localhost:8000/village-api/api/character/frequency/global`
- `http://localhost:8000/village-api/docs`

**Step 5: Install dependencies**

Add to your `requirements.txt`:

```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
pandas>=2.0.0
numpy>=1.24.0
scikit-learn>=1.3.0
networkx>=3.1
```

### Option 2: Include Routers Directly

**Step 1: Copy only router modules**

```bash
cp -r /path/to/villages-ML/api/character ./your_app/routers/
cp -r /path/to/villages-ML/api/village ./your_app/routers/
cp -r /path/to/villages-ML/api/compute ./your_app/routers/
# ... copy other router directories
```

**Step 2: Copy dependencies and models**

```bash
cp /path/to/villages-ML/api/dependencies.py ./your_app/
cp /path/to/villages-ML/api/models.py ./your_app/
cp /path/to/villages-ML/api/config.py ./your_app/
```

**Step 3: Update imports**

In each copied router file, update imports:

```python
# Before
from ..dependencies import get_db
from ..models import CharFrequency

# After
from your_app.dependencies import get_db
from your_app.models import CharFrequency
```

**Step 4: Register routers**

```python
# your_app/main.py
from fastapi import FastAPI
from your_app.routers.character import frequency, tendency
from your_app.routers.village import search

app = FastAPI()

app.include_router(frequency.router, prefix="/api")
app.include_router(tendency.router, prefix="/api")
app.include_router(search.router, prefix="/api")
```

---

## Production Deployment

### Using Docker

**Create `Dockerfile`:**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy API code
COPY api/ ./api/

# Copy database (or mount as volume)
COPY data/villages.db ./data/villages.db

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# Run application
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Create `docker-compose.yml`:**

```yaml
version: '3.8'

services:
  api:
    build: ..
    ports:
      - "8000:8000"
    volumes:
      - ./data/villages.db:/app/data/villages.db:ro  # Read-only database
    environment:
      - VILLAGES_DB_PATH=/app/data/villages.db
      - LOG_LEVEL=info
    restart: unless-stopped
    healthcheck:
      test: [ "CMD", "curl", "-f", "http://localhost:8000/health" ]
      interval: 30s
      timeout: 10s
      retries: 3
```

**Build and run:**

```bash
docker-compose up -d
```

**Test:**

```bash
curl http://localhost:8000/health
```

### Using Nginx Reverse Proxy

**Install Nginx:**

```bash
sudo apt-get install nginx
```

**Configure Nginx (`/etc/nginx/sites-available/village-api`):**

```nginx
server {
    listen 80;
    server_name api.yourdomain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;

    # SSL certificates (use Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.yourdomain.com/privkey.pem;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Proxy to FastAPI
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeout for long-running compute endpoints
        proxy_read_timeout 60s;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
    }

    # Increase body size for POST requests
    client_max_body_size 10M;
}
```

**Enable site:**

```bash
sudo ln -s /etc/nginx/sites-available/village-api /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Using Systemd Service

**Create service file (`/etc/systemd/system/village-api.service`):**

```ini
[Unit]
Description=Village Analysis API
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/village-api
Environment="PATH=/opt/village-api/venv/bin"
ExecStart=/opt/village-api/venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000 --workers 4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Enable and start:**

```bash
sudo systemctl daemon-reload
sudo systemctl enable village-api
sudo systemctl start village-api
sudo systemctl status village-api
```

---

## Configuration

### Environment Variables

Create `.env` file:

```bash
# Database
VILLAGES_DB_PATH=/path/to/villages.db

# API Configuration
API_TITLE="Guangdong Village Analysis API"
API_VERSION="1.0.0"
DEFAULT_RUN_ID="default"

# Pagination
DEFAULT_PAGE_SIZE=20
MAX_PAGE_SIZE=100

# Compute
COMPUTE_TIMEOUT=30
CACHE_TTL=300
CACHE_MAX_SIZE=100

# CORS
ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Logging
LOG_LEVEL=info
```

**Load in `config.py`:**

```python
import os
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("VILLAGES_DB_PATH", "../../data/villages.db")
API_TITLE = os.getenv("API_TITLE", "Village Analysis API")
DEFAULT_PAGE_SIZE = int(os.getenv("DEFAULT_PAGE_SIZE", "20"))
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
```

### Database Path Configuration

**Option 1: Relative path (development)**

```python
# api/dependencies.py
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "villages.db")
```

**Option 2: Absolute path (production)**

```python
DB_PATH = "/opt/village-api/data/villages.db"
```

**Option 3: Environment variable (recommended)**

```python
DB_PATH = os.getenv("VILLAGES_DB_PATH", "/opt/village-api/data/villages.db")
```

### CORS Configuration

**Development (allow all):**

```python
allow_origins=["*"]
```

**Production (restrict):**

```python
allow_origins=[
    "https://yourdomain.com",
    "https://www.yourdomain.com",
]
```

---

## Performance Optimization

### 1. Database Connection Pooling

Currently using `sqlite3.connect()` per request. For production, consider:

```python
# api/dependencies.py
import sqlite3
from contextlib import contextmanager

# Connection pool (simple implementation)
_connection_pool = []

@contextmanager
def get_db():
    if _connection_pool:
        conn = _connection_pool.pop()
    else:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row

    try:
        yield conn
    finally:
        _connection_pool.append(conn)
```

### 2. Increase Workers

For production, use multiple workers:

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

**Note:** SQLite has limited concurrency. For high traffic, consider:
- Read-only mode for database
- PostgreSQL/MySQL for write operations
- Separate read replicas

### 3. Cache Configuration

Adjust cache TTL and size in `api/compute/cache.py`:

```python
# Increase cache size for production
cache = TTLCache(maxsize=500, ttl=600)  # 500 entries, 10 minutes
```

### 4. Timeout Settings

Adjust timeout for compute endpoints:

```python
# api/compute/timeout.py
COMPUTE_TIMEOUT = 60  # Increase to 60 seconds for complex operations
```

### 5. Database Indexes

Ensure indexes exist for frequently queried columns:

```sql
CREATE INDEX IF NOT EXISTS idx_village_name ON 广东省自然村(自然村);
CREATE INDEX IF NOT EXISTS idx_city ON 广东省自然村(市级);
CREATE INDEX IF NOT EXISTS idx_county ON 广东省自然村(区县级);
```

---

## Security Considerations

### 1. CORS Restrictions

**Never use `allow_origins=["*"]` in production.**

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # Specific domain only
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
```

### 2. Rate Limiting

Add rate limiting middleware:

```bash
pip install slowapi
```

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/api/village/search")
@limiter.limit("10/minute")  # 10 requests per minute
async def search_villages(...):
    ...
```

### 3. Input Validation

Already implemented via Pydantic models. Ensure all endpoints use:
- `Query()` with constraints (min_length, max_length, ge, le)
- `Field()` with validation
- Pattern matching for enums

### 4. SQL Injection Prevention

Already using parameterized queries:

```python
# Good (current implementation)
cursor.execute("SELECT * FROM table WHERE name = ?", (name,))

# Bad (never do this)
cursor.execute(f"SELECT * FROM table WHERE name = '{name}'")
```

### 5. HTTPS Only

Use HTTPS in production:
- Obtain SSL certificate (Let's Encrypt)
- Configure Nginx with SSL
- Redirect HTTP to HTTPS

### 6. Authentication (Optional)

If needed, add API key authentication:

```python
from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader

API_KEY = os.getenv("API_KEY", "your-secret-key")
api_key_header = APIKeyHeader(name="X-API-Key")

def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key

@app.get("/api/protected")
def protected_endpoint(api_key: str = Depends(verify_api_key)):
    return {"message": "Authenticated"}
```

---

## Monitoring and Logging

### 1. Logging Configuration

Update `api/main.py`:

```python
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/village-api/api.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

@app.on_event("startup")
async def startup_event():
    logger.info("API starting up")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("API shutting down")
```

### 2. Request Logging Middleware

```python
import time
from fastapi import Request

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time

    logger.info(
        f"{request.method} {request.url.path} "
        f"status={response.status_code} duration={duration:.3f}s"
    )

    return response
```

### 3. Health Check Endpoint

Already implemented:

```python
@app.get("/health")
def health_check():
    return {"status": "healthy"}
```

Use for monitoring:

```bash
# Cron job to check health
*/5 * * * * curl -f http://localhost:8000/health || systemctl restart village-api
```

### 4. Metrics (Optional)

Add Prometheus metrics:

```bash
pip install prometheus-fastapi-instrumentator
```

```python
from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator().instrument(app).expose(app)
```

Access metrics at `http://localhost:8000/metrics`

---

## Troubleshooting

### Database Not Found

**Error:** `sqlite3.OperationalError: unable to open database file`

**Solution:**
1. Check database path in `dependencies.py`
2. Verify file exists: `ls -l /path/to/villages.db`
3. Check file permissions: `chmod 644 villages.db`

### CORS Errors

**Error:** `Access to fetch at 'http://localhost:8000' from origin 'http://localhost:5173' has been blocked by CORS policy`

**Solution:**
1. Add frontend origin to `allow_origins` in `main.py`
2. Restart API server

### Timeout Errors

**Error:** `408 Request Timeout`

**Solution:**
1. Reduce `sample_size` for subset operations
2. Use smaller `k_range` for clustering scans
3. Increase timeout in `compute/timeout.py`
4. Check if results are cached

### Import Errors

**Error:** `ModuleNotFoundError: No module named 'api'`

**Solution:**
1. Ensure running from correct directory
2. Use `python -m uvicorn api.main:app` instead of `uvicorn main:app`
3. Check PYTHONPATH

---

## Deployment Checklist

- [ ] Database path configured correctly
- [ ] CORS origins restricted to production domain
- [ ] HTTPS enabled with valid SSL certificate
- [ ] Environment variables set (`.env` file)
- [ ] Logging configured and working
- [ ] Health check endpoint accessible
- [ ] Rate limiting enabled (optional)
- [ ] Authentication configured (if needed)
- [ ] Nginx reverse proxy configured
- [ ] Systemd service enabled and running
- [ ] Firewall rules configured
- [ ] Monitoring and alerts set up
- [ ] Backup strategy for database
- [ ] Documentation updated with production URLs

---

## See Also

- [API Reference](API_REFERENCE.md) - Complete endpoint documentation
- [Frontend Integration Guide](FRONTEND_INTEGRATION_GUIDE.md) - Vue 3 integration
- [API Quick Reference](API_QUICK_REFERENCE.md) - Cheat sheet
- [FastAPI Documentation](https://fastapi.tiangolo.com/) - Official FastAPI docs