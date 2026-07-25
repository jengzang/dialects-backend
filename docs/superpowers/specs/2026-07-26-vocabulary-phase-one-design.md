# Vocabulary Phase One Design

## Goal

Add the first phase of vocabulary-list support: create `data/vocabulary.db`, define the storage model, and expose an authenticated upload API that imports one location's vocabulary entries from spreadsheet or document files.

This phase covers only data creation and replacement-on-upload. Query display, user editing screens, delete APIs, and reuse of generic `sql/admin` editing routes are intentionally left for later phases.

## Scope

Phase one includes:

- A new `vocabulary.db` SQLite database.
- Three tables: entries, locations, and permissions.
- A new upload API under `/api/vocabulary`.
- File parsers for table files and two document formats.
- Permission checks with two levels: `edit` and `manage`.
- Replacement behavior for repeat uploads with the same user and location short name.

Phase one does not include:

- Public or authenticated read/query APIs.
- General edit or delete APIs.
- Full permission-management APIs.
- UI behavior.
- Reuse of `sql/admin` routes for editing.

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
- `created_at`: creation time.
- `updated_at`: update time.

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
- `raw_location_json`: original frontend location JSON as text.
- `created_at`
- `updated_at`

Uniqueness:

- `(user_id, location_name)` is unique. Re-uploading the same user's same short name updates this table.

The optional location fields are modeled after the active `query_admin.db/query_user.db` `dialects` table fields: `簡稱`, `經緯度`, `省`, `市`, `縣`, `鎮`, `行政村`, `自然村`, `音典分區`, and `地圖集二分區`.

### `vocabulary_permissions`

This table controls who can upload and manage vocabulary data.

Columns:

- `id`: integer primary key.
- `user_id`: unique user id.
- `permission_level`: either `edit` or `manage`.
- `created_at`
- `updated_at`

Rules:

- Admin users are treated as `manage` even without a row.
- `edit` can upload files and later manage only that user's own data.
- `manage` can upload files and later manage the whole `vocabulary_entries` table.
- Users without a permission row cannot upload.

Because both `edit` and `manage` include upload capability, the upload endpoint only checks that the effective permission level is one of those two values.

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

- `models.py`: SQLAlchemy models for the three tables.
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
