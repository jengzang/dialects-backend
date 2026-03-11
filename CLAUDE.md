# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Dialect Compare Tool** - A FastAPI-based geolinguistic data analysis and visualization platform for Chinese dialect research. The system provides phonological data querying, analysis, and visualization capabilities for academic researchers studying Chinese dialects.

**Tech Stack**: FastAPI 0.116.1, Python 3.12+, SQLite (8 databases), Redis, Pandas, NumPy, Praat-parselmouth

## Running the Application

### Development Mode
```bash
# Set environment variable
export _RUN_TYPE=MINE  # or set in common/config.py

# Start with hot reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 5000

# Access at http://localhost:5000
```

### Production Mode (Multi-worker)
```bash
# Single process
uvicorn app.main:app --host 0.0.0.0 --port 5000

# Multi-worker (recommended for production)
uvicorn app.main:app --host 0.0.0.0 --port 5000 --workers 4

# Or with Gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:5000
```

### Docker Deployment
```bash
# Build and deploy
docker build -t myapp:latest .
docker run -p 5000:5000 -v ./data:/app/data myapp:latest

# Or use PowerShell deployment script
./deploy.ps1
```

### Testing
```bash
# Run integration tests
python test_praat_integration.py
python test_praat_setup.py

# Test specific modules
python test_pitch_module.py
```

## Architecture Overview

### Run Modes
The application supports three run modes (configured via `_RUN_TYPE` in `common/config.py`):
- **WEB**: Production mode with real Redis
- **MINE**: Development mode with local IP
- **EXE**: Packaged executable mode

### Database Architecture
The system uses **8 separate SQLite databases** for different purposes:
- `auth.db` - User authentication, sessions, permissions (256KB)
- `logs.db` - API logs, statistics, visits (variable size)
- `supplements.db` - User-submitted custom data (256KB)
- `dialects_user.db` / `dialects_admin.db` - Dialect data (489MB/503MB)
- `query_user.db` / `query_admin.db` - Query indexes (1.2MB each)
- `characters.db` - Middle Chinese phonology data (6.2MB)
- `villages.db` - Location coordinates (34MB)

**Key Design**: User/admin databases are separated to provide different data access levels.

### Database Connection Pool
- Managed by `app/sql/db_pool.py`
- Pre-initialized pools for frequently accessed databases
- Pool sizes: 5-10 connections per database
- Initialized at application startup in `app/main.py:lifespan()`

### Permission System
Fine-grained database permission control (`app/auth/models.py`, `app/sql/choose_db.py`):
- **Admin-only databases**: query_admin, dialects_admin, logs, supple, auth
- **Public databases**: query, dialects, spoken, village, chars, yubao
- Write permissions controlled by `user_db_permissions` table
- Permission checks in `get_db_connection()` function

### Multi-Process Logging System
Critical for production deployment with multiple workers:
- **5 independent queues** using `multiprocessing.Queue`:
  - `log_queue`: API usage logs (max 2000)
  - `keyword_log_queue`: Keyword logs (max 5000)
  - `statistics_queue`: API statistics (max 1000)
  - `html_visit_queue`: Page visits (max 500)
  - `summary_queue`: Usage summaries (max 1000)
- Batch writing strategy (3-50 records, 5-180s timeout)
- Managed by `app/logs/service/api_logger.py`
- Started/stopped in `app/main.py:lifespan()`

### Middleware Stack
Applied in order (see `app/main.py`):
1. **CORSMiddleware** - Cross-origin requests
2. **GZipMiddleware** - Response compression (>10KB)
3. **TrafficLoggingMiddleware** - Request/response logging
4. **ApiLoggingMiddleware** - API rate limiting and keyword logging

### File Management System
Unified file storage for all tools (`app/tools/file_manager.py`):
- **Storage location**: System temp directory `{temp}/fastapi_tools/`
- **Structure**: `{base_dir}/{tool_name}/{task_id}/`
- **Cleanup**: Automatic cleanup of files older than 12 hours on startup
- Used by: Praat, Check, Merge, Jyut2IPA tools

## Key Modules

### Authentication & Authorization
- **JWT tokens**: Access tokens (30 min) + Refresh tokens (30 days)
- **Session management**: `refresh_tokens` table tracks all active sessions
- **Multi-device control**: Max 10 active tokens per user
- **Online time tracking**: Frontend reports activity, backend aggregates
- **Admin endpoints**: `/admin/sessions/*` for session management

### API Rate Limiting
- **Unified system**: `ApiLimiter` dependency injection
- **Configuration**: `common/api_config.py` - `API_ROUTE_CONFIG` dict
- **Quotas**: 2000 req/hour (authenticated), 300 req/hour (anonymous)
- **Size limits**: 6MB (authenticated), 1MB (anonymous)

### Phonological Analysis
Core business logic for dialect research:
- **Phoneme analysis** (`/api/YinWei`): Phoneme-based queries
- **Middle Chinese** (`/api/ZhongGu`): Historical phonology mapping
- **Classification matrix** (`/api/phonology_classification_matrix`): Multi-dimensional analysis
- **Character search** (`/api/search_chars/`): Pronunciation lookup
- **Tone search** (`/api/search_tones/`): Tone system queries

### Praat Acoustic Analysis
Experimental phonetics backend for Chinese/dialect tone analysis:
- **Location**: `app/tools/praat/` (moved from `app/praat/`)
- **API prefix**: `/api/praat/*`
- **Two modes**: `single` (syllables) vs `continuous` (phrases)
- **Modules**: basic, pitch, intensity, formant, voice_quality, segments
- **Async jobs**: Upload → Job → Poll → Result workflow
- **Tone features**: Specialized for Chinese tone contour extraction
- **Dependencies**: Requires FFmpeg for audio normalization

### VillagesML Natural Village Analysis
Comprehensive geolinguistic analysis system for Guangdong Province villages:
- **Location**: `app/tools/VillagesML/`
- **API prefix**: `/api/villages/*`
- **Database**: `data/villages.db` (5.7GB, 45 tables, 285K+ villages)
- **Modules**: Character, semantic, spatial, clustering, n-grams, patterns, compute
- **ML models**: Word2Vec embeddings, KMeans/DBSCAN/GMM clustering, PMI scores
- **Compute endpoints**: Real-time clustering, semantic networks, feature extraction
- **Authentication**: Public for queries, login required for compute/admin endpoints
- **Documentation**: `app/tools/VillagesML/docs/`

### SQL Query Interface
Generic SQL query system for admin operations:
- **Query**: `POST /sql/query` - Read operations
- **Mutate**: `POST /sql/mutate` - Single record CUD
- **Batch**: `POST /sql/batch-mutate` - Bulk operations
- **Tree view**: `POST /sql/tree` - Hierarchical data queries
- **Permissions**: Admin-only for write operations

## Performance Optimizations

### Database Indexing
Auto-managed by `app/sql/index_manager.py`:
- 7 critical indexes on `dialects` table
- Composite index on `(漢字, 簡稱)` for character-location queries
- Indexes on `characters` table for Middle Chinese lookups
- **Performance gain**: 40-50% query speed improvement

### Query Optimization
- **N+1 elimination**: Batch queries instead of loops (99.9% reduction in query count)
- **Table scan merging**: UNION ALL for multi-feature queries (66% faster)
- **Connection pooling**: Pre-initialized pools reduce connection overhead
- **Redis caching**: 1-hour cache for phonology matrices, 10-min for queries

### Async Processing
- **Background logging**: Non-blocking log writes via queues
- **CPU-intensive tasks**: `run_in_threadpool()` for heavy computations
- **Scheduled tasks**: APScheduler for periodic cleanup

## Important Patterns

### Adding New API Endpoints
1. Define Pydantic schemas in `app/schemas/`
2. Implement business logic in `app/service/`
3. Create route in `app/routes/`
4. Register route in `app/routes/__init__.py:setup_routes()`
5. Add rate limit config to `common/api_config.py:API_ROUTE_CONFIG`

### Database Operations
```python
# Use connection pool
from app.sql.db_pool import get_db_pool
pool = get_db_pool(db_path)
with pool.get_connection() as conn:
    result = conn.execute(query)

# Check permissions
from app.sql.choose_db import get_db_connection
conn = get_db_connection(db_key, user, operation="read", auth_db=auth_db)
```

### Logging API Calls
```python
# Use ApiLimiter dependency (automatic logging)
from app.logs.service.api_limiter import ApiLimiter

@router.post("/my-endpoint")
async def my_endpoint(user: Optional[User] = Depends(ApiLimiter)):
    # Logging handled automatically by middleware
    pass
```

### File Storage (Tools)
```python
from app.tools.file_manager import file_manager

# Save uploaded file
task_dir = file_manager.get_task_dir(task_id, "praat")
file_path = file_manager.save_upload_file(task_id, "praat", file, filename)

# Get file path
path = file_manager.get_file_path(task_id, "praat", filename)

# Cleanup old files
deleted = file_manager.cleanup_old_files(max_age_hours=12)
```

### Module Organization

**Rule**: A module should be EITHER a file OR a package, never both simultaneously.

❌ **Wrong** (causes Python import conflicts):
```
mymodule.py
mymodule/__init__.py  # Conflict! Python will only use the package
```

✅ **Correct** (choose one approach):
```
# Option 1: Single-file module
mymodule.py

# Option 2: Package module
mymodule/
  __init__.py
  submodule1.py
  submodule2.py
```

**When to use a package**:
- Module content exceeds 500 lines
- Need to split into multiple submodules
- Require internal organizational structure

**When to use a file**:
- Simple module (< 500 lines)
- Single responsibility
- No need for submodules

**Prevention**: A pre-commit hook is installed at `.git/hooks/pre-commit` to detect and prevent module name conflicts.

## Configuration

### Environment Variables
- `_RUN_TYPE`: Run mode (WEB/MINE/EXE)
- `FILE_STORAGE_PATH`: Override default file storage location
- `REDIS_HOST`, `REDIS_PORT`: Redis connection (WEB mode only)

### Key Settings (`common/config.py`)
- `SECRET_KEY`: JWT signing key (MUST change in production)
- `REQUIRE_LOGIN`: Force authentication for all endpoints
- `MAX_USER_USAGE_PER_HOUR`: API rate limit for authenticated users
- `MAX_IP_USAGE_PER_HOUR`: API rate limit for anonymous users
- `BATCH_SIZE`: Log batch write size
- `CACHE_EXPIRATION_TIME`: Redis cache TTL

### API Route Configuration (`common/api_config.py`)
```python
API_ROUTE_CONFIG = {
    "/api/endpoint": {
        "rate_limit": True,
        "require_login": False,
        "log_params": True,
        "log_body": False,
    }
}
```

## Critical Constraints

### Praat Tool Specifications
The Praat acoustic analysis tool MUST follow specifications in the existing `claude.md` file:
- API prefix: `/api/praat/` (no versioning)
- Async job-based workflow (no synchronous analysis)
- Two modes: `single` and `continuous` with different segmentation strategies
- FFmpeg normalization required before Praat processing
- JSON output must be stable (no NaN/inf, use null)
- Tone features for Chinese/dialect analysis required

### Database Permissions
- Never bypass permission checks in `get_db_connection()`
- Admin-only databases must not be accessible to regular users
- Write operations require explicit permission grants in `user_db_permissions`

### Multi-Worker Compatibility
- Always use `multiprocessing.Queue` for shared state, never `queue.Queue`
- Database connections must use connection pools, not direct connections
- Redis operations must handle connection failures gracefully

### Security
- Never commit `SECRET_KEY` to version control
- Always validate user input with Pydantic schemas
- Use parameterized queries to prevent SQL injection
- Sanitize file uploads (check MIME types, file sizes)

## Common Issues

### "Database is locked" errors
- Ensure using connection pools (`app/sql/db_pool.py`)
- Check for long-running transactions
- Verify WAL mode is enabled on SQLite databases

### Logs not appearing in multi-worker mode
- Verify using `multiprocessing.Queue` in `api_logger.py`
- Check log worker processes are started in `lifespan()`
- Logs may have up to 180s delay due to batch writing

### Redis connection failures in development
- Set `_RUN_TYPE=MINE` to use fake Redis client
- Or install and start Redis locally

### FFmpeg not found (Praat tool)
- Install FFmpeg: `apt-get install ffmpeg` (Linux) or download from ffmpeg.org
- Verify in PATH: `ffmpeg -version`
- Docker: FFmpeg is included in Dockerfile

## Project Structure Notes

- `app/main.py`: Application entry point, lifespan management
- `app/routes/`: API endpoints (organized by feature)
- `app/service/`: Business logic layer
- `app/schemas/`: Pydantic models for request/response validation
- `app/auth/`: Authentication, authorization, session management
- `app/logs/`: Logging system (multi-process queues, schedulers)
- `app/sql/`: Database connection pools, query interfaces, permissions
- `app/tools/`: Modular tools (Praat, Check, Merge, Jyut2IPA, VillagesML)
- `common/`: Shared configuration, constants, utilities
- `data/`: SQLite database files (not in version control)
- `docs/`: Documentation files (organized by category - see docs/README.md)
- `test/`: Test scripts and utilities

### Critical File Constraints

1.  **No New Root Files:** Do not create new documentation or script files in the root directory.
2.  **Documentation Placement:** Any file explaining "how-to" or "architecture" must go into `docs/`.
3.  **Testing & Migration:** Any `.py` file intended for testing, environment setup, or database migration must go into `test/`.
4.  **Module Rule:** A module should be EITHER a file OR a package, never both simultaneously.

### File Organization Guidelines

* **Documentation:** ALL documentation files (including `.md` guides, technical specs, and manuals) MUST be placed in the `docs/` directory.
* **Scripts:** ALL test scripts (unit, integration, or setup tests) and data migration scripts MUST be placed in the `test/` directory.
* **Root Cleanliness:** Keep the project root clean. Only essential configuration files (e.g., `.gitignore`, `requirements.txt`, `pyproject.toml`) and the main entry point should reside in the root.


## Additional Resources

- Full README: `README.md` (comprehensive Chinese documentation)
- Praat specifications: `claude.md` (detailed API requirements)
- Memory notes: `.claude/projects/.../memory/MEMORY.md` (implementation history)
