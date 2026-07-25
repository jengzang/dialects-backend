# Vocabulary Phase One Design

## Goal

Add the first phase of vocabulary-list support: create `data/vocabulary.db`, define the storage model, and expose an authenticated upload API that imports one location's vocabulary entries from spreadsheet or document files.

This phase covers data creation, replacement-on-upload, and a vocabulary-scoped SQL editing/query surface under `/api/vocabulary/sql/*`. User-facing display APIs remain a later phase, but the SQL-style editor APIs can now support internal/admin editing workflows with row-level permission rules.

## Scope

Phase one includes:

- A new `vocabulary.db` SQLite database.
- Four tables: entries, locations, permissions, and operation logs.
- A new upload API under `/api/vocabulary`.
- A vocabulary-only SQL query/edit API under `/api/vocabulary/sql/*`.
- File parsers for table files and two document formats.
- Permission checks with two levels: `edit` and `manage`.
- Replacement behavior for repeat uploads with the same user and location short name.
- Operation logs for all vocabulary edit actions.

Phase one does not include:

- Full permission-management APIs.
- UI behavior.
- Raw SQL, DDL, tree APIs, or arbitrary `db_key`/database access.

## Database

`vocabulary.db` is the database name. It matches the existing project naming style used by `characters.db`, `villages.db`, and `yubao.db`.

### `vocabulary_entries`

This is the real vocabulary data table.

Columns:

- `id`: integer primary key.
- `user_id`: uploader id, filled from the authenticated user.
- `location_name`: location short name, copied from the uploaded location JSON.
- `standard_word`: standard written word or definition-like prompt. This replaces the less intuitive name `written`.
- `local_expression`: local dialect expression.
- `ipa`: IPA transcription.
- `notes`: optional note.
- `informations`: reserved text column, initially empty.
- `source_filename`: original upload filename.

Indexes:

- `(user_id, location_name)` for user-scoped replacement and later user editing.
- `location_name` for future query/read features.
- `standard_word` for future lookup.

### `vocabulary_locations`

This table stores one uploaded location metadata record per user and short name.

Columns:

- `id`: integer primary key.
- `user_id`: uploader id.
- `location_name`: required location short name.
- `coordinates`: required longitude/latitude string.
- `province`
- `city`
- `county`
- `town`
- `administrative_village`
- `natural_village`
- `yindian_region`: 音典分区.
- `atlas_region`: 地图集 or 方音图鉴分区.

Uniqueness:

- `(user_id, location_name)` is unique. Re-uploading the same user's same short name updates this table.

The optional location fields are modeled after the active `query_admin.db/query_user.db` `dialects` table fields: `簡稱`, `經緯度`, `省`, `市`, `縣`, `鎮`, `行政村`, `自然村`, `音典分區`, and `地圖集二分區`.

### `vocabulary_permissions`

This table controls who can upload and manage vocabulary data.

Columns:

- `id`: integer primary key.
- `user_id`: unique user id.
- `permission_level`: either `edit` or `manage`.

Rules:

- Admin users are treated as `manage` even without a row.
- `edit` can upload files and later manage only that user's own data.
- `manage` can upload files and later manage the whole `vocabulary_entries` table.
- Users without a permission row cannot upload.

Because both `edit` and `manage` include upload capability, the upload endpoint only checks that the effective permission level is one of those two values.

### `vocabulary_logs`

This table stores audit records for vocabulary edit operations.

Columns:

- `id`: integer primary key.
- `operation_id`: UUID for the user-level operation.
- `user_id`: acting user id.
- `permission_level`: effective permission at the time of operation.
- `source`: operation source, such as `upload`, `sql_editor`, `batch_mutate`, or `batch_replace`.
- `action`: operation action, such as `import`, `create`, `update`, `delete`, or `replace`.
- `table_name`: affected vocabulary table.
- `target_scope`: human-readable summary of the server-side scope applied.
- `affected_rows`: number of rows changed.
- `status`: operation status. The current implemented write paths record `success`.
- `payload_json`: serialized request/operation payload.
- `created_at`: log creation time.

Only `manage` users can query `vocabulary_logs`. Logs are system-written; they are not editable through the generic vocabulary SQL mutation APIs. Logs are operation-level, not row-level: one upload, batch mutation, or batch replace writes one log row regardless of how many vocabulary rows it affects.

## API

### `POST /api/vocabulary/upload`

Request type: `multipart/form-data`.

Fields:

- `file`: required uploaded file.
- `location`: required JSON string from the frontend.
- `parser_mode`: optional, one of `auto`, `table`, `doc_whitespace`, or `doc_bracket`. Default is `auto`.

Required location JSON fields:

- `location_name`
- `coordinates`

The API also accepts common aliases for location keys, including Chinese names such as `簡稱`, `简称`, `地名`, `經緯度`, and `经纬度`.

Response:

```json
{
  "success": true,
  "location_id": 1,
  "location_name": "息烽",
  "permission_level": "edit",
  "imported_count": 100,
  "deleted_existing_count": 100,
  "skipped_count": 0,
  "errors": [],
  "parser_mode": "table"
}
```

Errors:

- `401`: no authenticated user.
- `403`: authenticated user lacks `edit` or `manage` vocabulary permission.
- `400`: invalid location JSON, missing required location fields, unsupported file type, unparseable file, or no valid vocabulary rows.
- `422`: request body validation errors from FastAPI.
- `500`: unexpected database or server failure.

## Upload Replacement Rule

When a user uploads a file for a location short name that already has entries from the same user:

1. The endpoint starts one database transaction.
2. The location metadata row is inserted or updated.
3. Existing `vocabulary_entries` rows for `(user_id, location_name)` are deleted.
4. Newly parsed entries are inserted.
5. The transaction commits.

If parsing or inserting fails, the transaction rolls back. This prevents a partially deleted location vocabulary.

The phase-one rule is user scoped: an `edit` user's upload replaces only that user's rows for the same location name. `manage` privileges do not change upload replacement scope in this phase; broader management behavior is deferred to later editing APIs.

Upload writes one `vocabulary_logs` row with `source = upload`, `action = import`, the acting `user_id`, effective permission level, affected row count, filename, parser mode, location name, and deleted/reinserted counts.

### `GET /api/vocabulary/locations`

Reads location metadata for the dedicated vocabulary database.

Query parameters:

- `user_id`: optional. Only `manage` and admin users can use this to inspect a specific user's locations. `edit` users are always scoped to their own `user_id`.
- `location_name`: optional exact short-name filter.
- `page`: default `1`.
- `page_size`: default `50`, max `200`.

Response rows expose `user_id`, `location_name`, editable metadata fields, and `location_label`. They do not expose the internal location `id`.

### `PATCH /api/vocabulary/locations/{location_name}`

Updates metadata for an existing vocabulary location. `location_name` is the path identity and cannot be changed by this API.

Body fields are optional, but at least one must be present:

- `coordinates`
- `province`
- `city`
- `county`
- `town`
- `administrative_village`
- `natural_village`
- `yindian_region`
- `atlas_region`

Rules:

- `coordinates`, if supplied, cannot be empty.
- `edit` users can update only the matching `(current_user.id, location_name)` row. Passing another `user_id` returns `403`.
- `manage` and admin users can update any user's row. If more than one row has the same `location_name`, the request must include `?user_id=...` to disambiguate.
- Successful updates write one `vocabulary_logs` row with `source = location_editor`, `action = update_location`, and `table_name = vocabulary_locations`.

## Vocabulary SQL API

All vocabulary SQL editor APIs are mounted under `/api/vocabulary/sql/*` and operate only on `vocabulary.db`. Requests do not include `db_key`.

Initial endpoints:

- `POST /api/vocabulary/sql/query`
- `GET /api/vocabulary/sql/query/columns`
- `GET /api/vocabulary/sql/query/count`
- `GET /api/vocabulary/sql/distinct/{table_name}/{column}`
- `POST /api/vocabulary/sql/distinct-query`
- `POST /api/vocabulary/sql/mutate`
- `POST /api/vocabulary/sql/batch-mutate`
- `POST /api/vocabulary/sql/batch-replace-preview`
- `POST /api/vocabulary/sql/batch-replace-execute`

Table exposure:

- `vocabulary_entries`: readable/editable.
- `vocabulary_locations`: readable/editable.
- `vocabulary_logs`: readable by `manage` only.
- `vocabulary_permissions`: not exposed through `/api/vocabulary/sql/*`.

Permission rules:

- `manage` can query and edit all exposed editable rows.
- `edit` can query and edit only rows where `user_id = current_user.id`.
- Create operations ignore any submitted `user_id` and force `user_id = current_user.id`.
- `user_id` and `id` are not mutable through generic edit endpoints.
- `batch-replace-preview` and `batch-replace-execute` use the same server-side `WHERE` builder, so preview and execution have the same row scope.
- All mutation, batch mutation, batch replace, upload, permission admin, and dedicated location metadata updates write one operation-level `vocabulary_logs` row.

## Parsers

All parsers output the same normalized fields:

- `standard_word`
- `local_expression`
- `ipa`
- `notes`

Rows with both `standard_word` and `local_expression` empty are skipped. Rows missing any of the first three fields produce row-level errors.

### Table Files

Supported extensions:

- `.xlsx`
- `.xls`
- `.csv`
- `.tsv`

The reference files in `tests/` use these headers:

- `written`
- `vocabulary`
- `ipa`
- `notes`

Column matching is tolerant:

- `standard_word`: `standard_word`, `written`, `释义`, `釋義`, `书面`, `書面`, `书面词条`, `書面詞條`, `词条`, `詞條`, `meaning`.
- `local_expression`: `local_expression`, `vocabulary`, `当地讲法`, `當地講法`, `方言词`, `方言詞`, `方言讲法`, `方言講法`, `local`.
- `ipa`: `ipa`, `IPA`, `音标`, `音標`, `国际音标`, `國際音標`.
- `notes`: `notes`, `note`, `注释`, `註釋`, `备注`, `備註`, `说明`, `說明`.

### Document Whitespace Format

Supported extensions:

- `.docx`
- `.doc`

Each paragraph is one vocabulary row. The four fields are separated by spaces, tabs, or line breaks inside the paragraph. Each row must parse into at least the first three fields; a fourth field becomes `notes`.

For `.docx`, paragraph boundaries are preserved as record boundaries. If fields are placed on separate lines within the same paragraph, the first three non-empty lines are treated as `standard_word`, `local_expression`, and `ipa`; remaining lines are joined as `notes`. If a record is a single line, whitespace separates the fields.

### Document Bracket Format

Supported extensions:

- `.docx`
- `.doc`

Each paragraph is one vocabulary row:

- Plain text outside brackets is `standard_word`.
- `[]` contains `ipa`.
- `{}` contains `notes`.
- `()` or `（）` contains `local_expression`.

## Architecture

New code should be isolated under `app/service/vocabulary/`:

- `models.py`: SQLAlchemy models for the vocabulary tables.
- `database.py`: engine, session dependency, and schema migration.
- `permissions.py`: effective permission lookup.
- `location.py`: location JSON normalization.
- `parser.py`: file parsing and normalized row validation.
- `service.py`: transactional upload workflow.

API schemas should live in `app/schemas/vocabulary.py`.

Routes should live in `app/routes/vocabulary.py` and be registered in `app/routes/__init__.py` under `/api/vocabulary`.

Startup migration should be called from `app/lifecycle/startup.py` when `AUTO_MIGRATE` is enabled, matching the existing supplements/logs migration style.

## Tests

Focused tests should cover:

- Table parser accepts the three reference `.xlsx` files and maps `written` to `standard_word`.
- Column aliases normalize to the four internal fields.
- Bracket document parser extracts plain text, `[]`, `{}`, and `()`/`（）`.
- Location JSON aliases normalize required location fields.
- Permission logic treats admin as `manage`, accepts `edit` and `manage`, and rejects missing permissions.
- Upload workflow replaces existing entries for the same `(user_id, location_name)` while updating location metadata.
- Route registration exposes `/api/vocabulary/upload`.

Tests may use temporary SQLite databases and direct service calls for transaction behavior. Route-level tests can use FastAPI dependency overrides where practical.
