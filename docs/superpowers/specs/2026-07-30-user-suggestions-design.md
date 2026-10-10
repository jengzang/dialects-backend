# Site Suggestions Storage and API Design

## Context

The backend stores user-contributed supplemental data in `data/supplements.db`.
That database is already managed through SQLAlchemy models in
`app/service/user/core/models.py`, with startup schema checks in
`app/service/user/core/database.py` and `app/lifecycle/startup.py`.

The feature adds a site-level suggestion channel. It is separate from the
existing structured dialect-data submissions in `informations`, because a
suggestion is closer to feedback or a lightweight work item than to a dialect
record. Authentication is optional; login details are attribution only.

## Goals

- Let anyone submit a site-level suggestion, including anonymous visitors.
- If the requester is logged in, record their `user_id` and `username`.
- Store suggestions in `supplements.db` through the existing ORM pattern.
- Give administrators a simple triage surface: list, filter, and update status.
- Keep the first version small enough to implement and test safely.

## Non-Goals

- No threaded comments or conversation history in the first version.
- No public voting, reactions, or duplicate suggestion merging.
- No email notification workflow.
- No frontend UI design in this spec.

## Data Model

Add an ORM model named `UserSuggestion` mapped to `user_suggestions`. These are
internal legacy names; product and API semantics should use neutral
`suggestions`.

Recommended SQL shape:

```sql
CREATE TABLE user_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username VARCHAR(100),
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    category VARCHAR(50) NOT NULL DEFAULT 'general',
    source_path VARCHAR(300),
    context_json TEXT,
    contact VARCHAR(200),
    image_base64 TEXT,
    submitter_ip VARCHAR(45),
    user_agent VARCHAR(300),
    recent_api TEXT,
    status VARCHAR(30) NOT NULL DEFAULT 'open',
    priority VARCHAR(20) NOT NULL DEFAULT 'normal',
    admin_note TEXT,
    handled_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

Indexes:

```sql
CREATE INDEX idx_user_suggestions_user_id ON user_suggestions(user_id);
CREATE INDEX idx_user_suggestions_status ON user_suggestions(status);
CREATE INDEX idx_user_suggestions_category ON user_suggestions(category);
CREATE INDEX idx_user_suggestions_created_at ON user_suggestions(created_at);
```

Field notes:

- `user_id` and `username` are nullable. Anonymous suggestions leave them empty.
- `contact` is optional and intended for anonymous visitors who want follow-up.
- `image_base64` is an optional screenshot data URL. It supports
  `data:image/webp;base64,...`, `data:image/png;base64,...`, and
  `data:image/jpeg;base64,...`. The API limits the field to 1MB.
- `submitter_ip` and `user_agent` support abuse investigation and debugging.
- `context_json` stores optional structured client context as JSON text.
- `recent_api` stores a JSON array snapshot of up to 10 recent API calls, each
  shaped as `{"name": "/api/path", "time": "2026-08-01T12:30:21", "duration": 0.132}`.
  It does not store status code, request body, query parameters, or response data.
- `category` is free text up to 50 characters, defaulting to `general`; the API
  should not enforce a closed category list.
- `status` values: `open`, `reviewing`, `accepted`, `rejected`, `done`.
- `priority` values: `low`, `normal`, `high`.

## User API

Register user-facing routes under the existing `/api` prefix.

### Submit Suggestion

`POST /api/suggestions`

Authentication is optional. The route should call `get_current_user`; if it
returns a user, persist `user_id` and `username`. If it returns `None`, accept
the suggestion as anonymous.

Request:

```json
{
  "title": "地图筛选希望保留上次选择",
  "content": "每次切换页面后筛选条件会重置，希望能记住。",
  "category": "feature",
  "source_path": "/map",
  "context": {
    "region": "嶺南-珠江",
    "client_version": "web-2026-07-30"
  },
  "contact": "optional@example.com",
  "image_base64": "data:image/webp;base64,..."
}
```

Response:

```json
{
  "success": true,
  "id": 123,
  "message": "建议已提交"
}
```

Validation:

- `title`: 1 to 200 characters after trimming.
- `content`: 1 to 5000 characters after trimming.
- `category`: optional free text, 1 to 50 characters after trimming; defaults to
  `general`.
- `source_path`: optional, max 300 characters.
- `contact`: optional, max 200 characters.
- `image_base64`: optional screenshot data URL, max 1MB, supporting webp, png,
  and jpeg.
- `context`: optional JSON object; serialize to `context_json`.

Recent API snapshot:

- If a logged-in user submits the suggestion, query `auth.db.api_usage_logs` by
  `user_id` first, newest first, up to 10 rows.
- If the logged-in user's rows provide fewer than 10 entries, fill the remaining
  slots by `submitter_ip`, newest first, excluding already selected log ids.
- If the submitter is anonymous, query by `submitter_ip` only.
- Store only `name`, `time`, and `duration` for each row.
- If `auth.db` lookup fails, suggestion submission should still succeed with
  `recent_api` set to `[]`.

### My Suggestions

`GET /api/suggestions/my?status=open&page=1&page_size=20`

Requires login. Anonymous users cannot query prior anonymous suggestions because
there is no stable identity to authorize against.
This endpoint keeps responses lightweight and does not include `image_base64`.

Response:

```json
{
  "success": true,
  "total": 1,
  "items": [
    {
      "id": 123,
      "title": "地图筛选希望保留上次选择",
      "content": "每次切换页面后筛选条件会重置，希望能记住。",
      "category": "feature",
      "source_path": "/map",
      "status": "open",
      "priority": "normal",
      "admin_note": null,
      "recent_api": [],
      "created_at": "2026-07-30T10:00:00",
      "updated_at": "2026-07-30T10:00:00"
    }
  ]
}
```

## Admin API

Register admin routes under `/admin/suggestions`.

### List Suggestions

`GET /admin/suggestions?status=open&category=feature&page=1&page_size=50`

Requires `get_current_admin_user`.

Filters:

- `status`
- `category`
- `user_id`
- `q`, searching `title`, `content`, `username`, and `contact`

Sort order: newest first by `created_at`, then `id`.
Admin responses include `image_base64` so screenshots can be inspected during
triage.

### Update Suggestion

`PATCH /admin/suggestions/{id}`

Request:

```json
{
  "status": "reviewing",
  "priority": "high",
  "admin_note": "需要前端评估是否已有本地缓存方案"
}
```

Behavior:

- Only admins can update.
- If `status` is changed to `accepted`, `rejected`, or `done`, set `handled_at`.
- Always update `updated_at`.

## Components

Add or update these modules:

- `app/service/user/core/models.py`: add `UserSuggestion`.
- `app/service/user/core/database.py`: add `migrate_user_suggestions_table()`.
- `app/lifecycle/startup.py`: call the new migration from the supplements schema check.
- `app/schemas/user/suggestions.py`: user and admin Pydantic schemas.
- `app/service/user/suggestion.py`: create and user-list service functions.
- `app/service/admin/suggestions.py`: admin list and update service functions.
- `app/routes/user/suggestions.py`: `/api/suggestions` routes.
- `app/routes/admin/suggestions.py`: `/admin/suggestions` routes.
- `app/routes/__init__.py` and `app/routes/admin/__init__.py`: register routers.

## Error Handling

- `400`: invalid status, priority, page, or page size.
- `401`: unauthenticated access to `/api/suggestions/my`.
- `403`: non-admin access to admin routes.
- `404`: updating a suggestion id that does not exist.
- `422`: Pydantic validation errors.
- `500`: unexpected persistence failure, with rollback.

## Testing

Add focused tests using temporary SQLite databases and FastAPI `TestClient` where
practical:

- Anonymous submit succeeds and stores no `user_id`.
- Logged-in submit stores `user_id` and `username`.
- Custom category strings are accepted.
- Submitting a suggestion snapshots recent API rows from `auth.db`, using user id
  first and IP fallback/fill to reach up to 10 rows.
- Logged-in user can list only their own suggestions.
- Anonymous visitor cannot call `/api/suggestions/my`.
- Admin list supports `status` and `category` filters.
- Admin update changes status, priority, note, `handled_at`, and `updated_at`.
- Startup migration creates the table and indexes idempotently.

## Open Decisions

The initial design accepts anonymous suggestions. If abuse becomes a problem,
the next step should be route-level rate limiting by IP and possibly a CAPTCHA
on the frontend, not a schema change.
