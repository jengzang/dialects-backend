import asyncio
import json
import sqlite3
import threading
from collections.abc import Iterable
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.common.config import SQL_QUERY_MAX_PAGE
from app.common.path import VOCABULARY_DB_PATH
from app.redis_client import redis_client
from app.schemas.vocabulary_sql import (
    BatchMutationParams,
    BatchReplaceExecuteParams,
    BatchReplacePreviewParams,
    DistinctQueryRequest,
    MutationParams,
    QueryParams,
)
from app.service.auth.core.dependencies import get_current_user
from app.service.auth.database.models import User
from app.service.logging.dependencies import ApiLimiter
from app.service.vocabulary.database import get_db as get_vocabulary_db
from app.service.vocabulary.database import raise_vocabulary_database_busy_if_locked
from app.service.vocabulary.logging import record_vocabulary_log
from app.service.vocabulary.permissions import get_effective_permission_level
from app.service.vocabulary.models import VocabularyLocation


router = APIRouter()

EDITABLE_TABLES = {"vocabulary_entries"}
ALLOWED_TABLES = EDITABLE_TABLES
OWNED_TABLES = {"vocabulary_entries"}
CREATE_PROTECTED_COLUMNS = frozenset({"id", "user_id"})
UPDATE_PROTECTED_COLUMNS = frozenset({"id", "user_id", "location_name"})
EDIT_FORBIDDEN_ACTIONS = {"batch_delete"}

_SCHEMA_CACHE: dict[str, set[str]] = {}
_SCHEMA_LOCK = threading.Lock()


def _quote_identifier(name: str) -> str:
    return f'"{name}"'


def _load_columns(table_name: str, db_path: str) -> set[str]:
    cache_key = f"{db_path}:{table_name}"
    with _SCHEMA_LOCK:
        if cache_key in _SCHEMA_CACHE:
            return _SCHEMA_CACHE[cache_key]

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
        columns = {row[1] for row in rows}
    finally:
        conn.close()

    with _SCHEMA_LOCK:
        _SCHEMA_CACHE[cache_key] = columns
    return columns


def _connection(db: Session):
    conn = db.connection().connection
    conn.row_factory = None
    return conn


def _require_table_access(
    user: User | None,
    table_name: str,
    *,
    write: bool = False,
    db: Session | None = None,
) -> str:
    if table_name not in ALLOWED_TABLES:
        raise HTTPException(status_code=400, detail=f"无效的词表表名: {table_name}")

    permission_level = get_effective_permission_level(db, user) if write else "public"
    if write and table_name not in EDITABLE_TABLES:
        raise HTTPException(status_code=403, detail="该表不允许通过词表 SQL 接口编辑")
    return permission_level


def _validate_columns(
    table_name: str,
    columns: Iterable[str],
    field_name: str,
    *,
    db_path: str = VOCABULARY_DB_PATH,
    allow_rowid: bool = False,
) -> set[str]:
    allowed = _load_columns(table_name, db_path)
    invalid = []
    for col in columns:
        if col is None:
            continue
        if allow_rowid and isinstance(col, str) and col.lower() == "rowid":
            continue
        if col not in allowed:
            invalid.append(col)
    if invalid:
        raise HTTPException(status_code=400, detail=f"无效的{field_name}: {', '.join(map(str, invalid))}")
    return allowed


def _validate_mutable_columns(
    table_name: str,
    columns: Iterable[str],
    field_name: str,
    *,
    db_path: str = VOCABULARY_DB_PATH,
    protected_columns: frozenset[str] = UPDATE_PROTECTED_COLUMNS,
) -> None:
    _validate_columns(table_name, columns, field_name, db_path=db_path)
    protected = [col for col in columns if col in protected_columns]
    if protected:
        raise HTTPException(status_code=400, detail=f"不允许修改字段: {', '.join(protected)}")


def _require_write_action_access(permission_level: str, action: str) -> None:
    if permission_level == "edit" and action in EDIT_FORBIDDEN_ACTIONS:
        raise HTTPException(status_code=403, detail="edit 用户不能通过词表 SQL 接口批量删除词条")


def _scope_clause(table_name: str, permission_level: str, user: User | None) -> tuple[list[str], list[Any], str]:
    if table_name in OWNED_TABLES and permission_level == "edit":
        return ["user_id = ?"], [user.id], f"user_id = {user.id}"
    return [], [], "all rows"


def _build_filter_clauses(filters: dict[str, list[Any]], values: list[Any]) -> list[str]:
    clauses = []
    for col, val_list in filters.items():
        if not val_list:
            continue
        has_empty = None in val_list
        normal_values = [value for value in val_list if value is not None]
        parts = []
        if normal_values:
            placeholders = ",".join(["?"] * len(normal_values))
            parts.append(f"{_quote_identifier(col)} IN ({placeholders})")
            values.extend(normal_values)
        if has_empty:
            col_q = _quote_identifier(col)
            parts.append(f"({col_q} IS NULL OR {col_q} = '')")
        if parts:
            clauses.append(f"({' OR '.join(parts)})")
    return clauses


def _build_search_clause(search_text: str | None, search_columns: list[str], values: list[Any]) -> list[str]:
    if not search_text or not search_columns:
        return []
    like_pattern = f"%{search_text}%"
    parts = []
    for col in search_columns:
        parts.append(f"{_quote_identifier(col)} LIKE ?")
        values.append(like_pattern)
    return [f"({' OR '.join(parts)})"] if parts else []


def _build_query_where(
    *,
    table_name: str,
    permission_level: str,
    user: User | None,
    filters: dict[str, list[Any]],
    search_text: str | None,
    search_columns: list[str],
) -> tuple[list[str], list[Any], str]:
    clauses, values, scope_description = _scope_clause(table_name, permission_level, user)
    clauses.extend(_build_filter_clauses(filters, values))
    clauses.extend(_build_search_clause(search_text, search_columns, values))
    return clauses, values, scope_description


def _build_batch_replace_where(
    *,
    params: BatchReplacePreviewParams,
    permission_level: str,
    user: User,
) -> tuple[list[str], list[Any], str]:
    clauses, values, scope_description = _build_query_where(
        table_name=params.table_name,
        permission_level=permission_level,
        user=user,
        filters=params.filters,
        search_text=params.search_text,
        search_columns=params.search_columns,
    )

    match_conditions = []
    if params.is_empty_search:
        for col in params.columns:
            col_q = _quote_identifier(col)
            match_conditions.append(f"({col_q} IS NULL OR {col_q} = '')")
    else:
        if params.match_mode == "exact":
            for col in params.columns:
                match_conditions.append(f"{_quote_identifier(col)} = ?")
                values.append(params.find_text)
        else:
            for col in params.columns:
                match_conditions.append(f"{_quote_identifier(col)} LIKE ?")
                values.append(f"%{params.find_text}%")

    if match_conditions:
        clauses.append(f"({' OR '.join(match_conditions)})")
    return clauses, values, scope_description


def _where_sql(clauses: list[str]) -> str:
    return " AND ".join(clauses) if clauses else "1=1"


def _row_to_dict(cursor, row) -> dict[str, Any]:
    result = {}
    for index, description in enumerate(cursor.description):
        column_name = "rowid" if description[0] == "__rowid__" else description[0]
        result[column_name] = row[index]
    return result


def _fetch_one_row_snapshot(
    cursor,
    *,
    table_name: str,
    clauses: list[str],
    values: list[Any],
) -> dict[str, Any] | None:
    cursor.execute(
        f"SELECT rowid AS __rowid__, * FROM {_quote_identifier(table_name)} WHERE {_where_sql(clauses)} LIMIT 1",
        values,
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return _row_to_dict(cursor, row)


def _select_columns(snapshot: dict[str, Any] | None, columns: Iterable[str], pk_column: str) -> dict[str, Any] | None:
    if snapshot is None:
        return None
    selected = {pk_column: snapshot.get(pk_column)}
    for column in columns:
        selected[column] = snapshot.get(column)
    return selected


def _sanitize_create_data(record: dict[str, Any], user: User, _permission_level: str) -> dict[str, Any]:
    data = dict(record)
    data.pop("id", None)
    data["user_id"] = user.id
    return data


def _validate_entry_fields(
    data: dict[str, Any],
    db: Session,
    user_id: int,
    *,
    existing: dict[str, Any] | None = None,
) -> None:
    merged = {**existing, **data} if existing else dict(data)

    if existing is None:
        loc = db.query(VocabularyLocation).filter(
            VocabularyLocation.user_id == user_id,
            VocabularyLocation.location_name == merged.get("location_name", ""),
        ).first()
        if loc is None:
            raise HTTPException(status_code=400, detail="地点不存在，请先创建地点")

    if "standard_word" in data:
        if not str(data["standard_word"]).strip():
            raise HTTPException(status_code=400, detail="standard_word 不能为空")

    if "ipa" in data or "local_expression" in data:
        ipa = str(merged.get("ipa", "")).strip()
        le = str(merged.get("local_expression", "")).strip()
        if not ipa and not le:
            raise HTTPException(status_code=400, detail="ipa 和 local_expression 至少需要有一个非空")


def _log_write(
    db: Session,
    *,
    user: User,
    permission_level: str,
    source: str,
    action: str,
    table_name: str,
    target_scope: str,
    affected_rows: int,
    payload: dict[str, Any],
) -> None:
    record_vocabulary_log(
        session=db,
        user_id=user.id,
        permission_level=permission_level,
        source=source,
        action=action,
        table_name=table_name,
        target_scope=target_scope,
        affected_rows=affected_rows,
        payload=payload,
    )


# ---------------------------------------------------------------------------
# Sync helpers for read endpoints (raw sqlite3 connections, thread-safe)
# ---------------------------------------------------------------------------


def _get_db_path(db: Session) -> str:
    return db.get_bind().url.database


def _query_table_sync(
    params: QueryParams,
    user: User | None,
    permission_level: str,
    db_path: str,
) -> dict:
    clauses, values, _ = _build_query_where(
        table_name=params.table_name,
        permission_level=permission_level,
        user=user,
        filters=params.filters,
        search_text=params.search_text,
        search_columns=params.search_columns,
    )
    table_q = _quote_identifier(params.table_name)
    where_clause = _where_sql(clauses)
    order_clause = ""
    if params.sort_by:
        direction = "DESC" if params.sort_desc else "ASC"
        order_clause = f" ORDER BY {_quote_identifier(params.sort_by)} {direction}"
    offset = (params.page - 1) * params.page_size

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT rowid, * FROM {table_q} WHERE {where_clause}{order_clause} LIMIT ? OFFSET ?",
            values + [params.page_size, offset],
        )
        rows = [_row_to_dict(cursor, row) for row in cursor.fetchall()]
        cursor.execute(f"SELECT COUNT(*) FROM {table_q} WHERE {where_clause}", values)
        total = cursor.fetchone()[0]
    finally:
        conn.close()

    return {"data": rows, "total": total, "page": params.page}


def _get_column_info_sync(table_name: str, db_path: str) -> dict:
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
        return {
            "table": table_name,
            "columns": [
                {
                    "name": row[1],
                    "type": row[2],
                    "notnull": bool(row[3]),
                    "pk": bool(row[5]),
                    "default_value": row[4],
                }
                for row in rows
            ],
        }
    finally:
        conn.close()


def _get_table_count_sync(
    table_name: str,
    permission_level: str,
    user: User | None,
    filter_column: str | None,
    filter_value: str | None,
    db_path: str,
) -> int:
    filters = {}
    if filter_column is not None:
        filters[filter_column] = [filter_value]
    clauses, values, _ = _build_query_where(
        table_name=table_name,
        permission_level=permission_level,
        user=user,
        filters=filters,
        search_text=None,
        search_columns=[],
    )
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute(
            f"SELECT COUNT(*) FROM {_quote_identifier(table_name)} WHERE {_where_sql(clauses)}",
            values,
        )
        return cursor.fetchone()[0]
    finally:
        conn.close()


def _get_distinct_values_sync(
    table_name: str, column: str, permission_level: str, user: User | None, db_path: str
) -> list:
    clauses, values, _ = _build_query_where(
        table_name=table_name,
        permission_level=permission_level,
        user=user,
        filters={},
        search_text=None,
        search_columns=[],
    )
    col_q = _quote_identifier(column)
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute(
            f"SELECT DISTINCT {col_q} FROM {_quote_identifier(table_name)} "
            f"WHERE {_where_sql(clauses)} ORDER BY {col_q} LIMIT 1000",
            values,
        )
        return [row[0] for row in cursor.fetchall() if row[0] is not None]
    finally:
        conn.close()


def _get_distinct_query_values_sync(
    req: DistinctQueryRequest, permission_level: str, user: User | None, db_path: str
) -> list:
    context_filters = {k: v for k, v in req.current_filters.items() if k != req.target_column}
    clauses, values, _ = _build_query_where(
        table_name=req.table_name,
        permission_level=permission_level,
        user=user,
        filters=context_filters,
        search_text=req.search_text,
        search_columns=req.search_columns,
    )
    target_col_q = _quote_identifier(req.target_column)
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute(
            f"SELECT DISTINCT {target_col_q} FROM {_quote_identifier(req.table_name)} "
            f"WHERE {_where_sql(clauses)} ORDER BY {target_col_q} LIMIT 1000",
            values,
        )
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Read endpoints
# ---------------------------------------------------------------------------


@router.post("/query")
async def query_table(
    params: QueryParams,
    user: Optional[User] = Depends(ApiLimiter),
    db: Session = Depends(get_vocabulary_db),
):
    permission_level = _require_table_access(user, params.table_name)
    db_path = _get_db_path(db)
    await asyncio.to_thread(_validate_columns, params.table_name, params.filters.keys(), "filters字段", db_path=db_path)
    await asyncio.to_thread(_validate_columns, params.table_name, params.search_columns, "search_columns", db_path=db_path)
    if params.sort_by:
        await asyncio.to_thread(_validate_columns, params.table_name, [params.sort_by], "sort_by", db_path=db_path)

    if not (user and user.role == "admin") and params.page_size > SQL_QUERY_MAX_PAGE:
        raise HTTPException(status_code=400, detail=f"page_size cannot exceed {SQL_QUERY_MAX_PAGE}")

    try:
        return await asyncio.to_thread(_query_table_sync, params, user, permission_level, db_path)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"查询失败: {exc}") from exc


@router.get("/query/columns")
async def get_column_info(
    table_name: str = "vocabulary_entries",
    user: Optional[User] = Depends(ApiLimiter),
    db: Session = Depends(get_vocabulary_db),
):
    _require_table_access(user, table_name)

    cache_key = f"vocab_sql_columns:{table_name}"
    try:
        cached = await redis_client.get(cache_key)
        if cached is not None:
            return json.loads(cached)
    except Exception:
        pass

    db_path = _get_db_path(db)
    result = await asyncio.to_thread(_get_column_info_sync, table_name, db_path)

    try:
        await redis_client.setex(cache_key, 3600, json.dumps(result))
    except Exception:
        pass

    return result


@router.get("/query/count")
async def get_table_count(
    table_name: str = "vocabulary_entries",
    filter_column: str | None = None,
    filter_value: str | None = None,
    user: Optional[User] = Depends(ApiLimiter),
    db: Session = Depends(get_vocabulary_db),
):
    permission_level = _require_table_access(user, table_name)
    db_path = _get_db_path(db)
    if filter_column is not None:
        await asyncio.to_thread(_validate_columns, table_name, [filter_column], "filter_column", db_path=db_path)

    cache_key = f"vocab_sql_count:{table_name}"
    if filter_column is not None:
        cache_key += f":{filter_column}:{filter_value}"

    try:
        cached = await redis_client.get(cache_key)
        if cached is not None:
            return {"count": int(cached)}
    except Exception:
        pass

    count = await asyncio.to_thread(
        _get_table_count_sync,
        table_name,
        permission_level,
        user,
        filter_column,
        filter_value,
        db_path,
    )

    try:
        await redis_client.setex(cache_key, 3600, str(count))
    except Exception:
        pass

    return {"count": count}


@router.get("/distinct/{table_name}/{column}")
async def get_distinct_path_values(
    table_name: str,
    column: str,
    user: Optional[User] = Depends(ApiLimiter),
    db: Session = Depends(get_vocabulary_db),
):
    permission_level = _require_table_access(user, table_name)
    db_path = _get_db_path(db)
    await asyncio.to_thread(_validate_columns, table_name, [column], "column", db_path=db_path)
    values = await asyncio.to_thread(_get_distinct_values_sync, table_name, column, permission_level, user, db_path)
    return {"values": values}


@router.post("/distinct-query")
async def get_distinct_query_values(
    req: DistinctQueryRequest,
    user: Optional[User] = Depends(ApiLimiter),
    db: Session = Depends(get_vocabulary_db),
):
    permission_level = _require_table_access(user, req.table_name)
    db_path = _get_db_path(db)
    await asyncio.to_thread(_validate_columns, req.table_name, [req.target_column], "target_column", db_path=db_path)
    await asyncio.to_thread(_validate_columns, req.table_name, req.current_filters.keys(), "current_filters字段", db_path=db_path)
    await asyncio.to_thread(_validate_columns, req.table_name, req.search_columns, "search_columns", db_path=db_path)
    values = await asyncio.to_thread(_get_distinct_query_values_sync, req, permission_level, user, db_path)
    return {"values": values}


# ---------------------------------------------------------------------------
# Write endpoints
# ---------------------------------------------------------------------------


@router.post("/mutate")
async def mutate_table(
    params: MutationParams,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_vocabulary_db),
):
    permission_level = _require_table_access(current_user, params.table_name, write=True, db=db)
    _require_write_action_access(permission_level, params.action)
    _validate_columns(params.table_name, [params.pk_column], "pk_column", allow_rowid=True)
    table_q = _quote_identifier(params.table_name)
    pk_q = _quote_identifier(params.pk_column)
    conn = _connection(db)
    cursor = conn.cursor()
    try:
        if params.action == "create":
            data = _sanitize_create_data(params.data, current_user, permission_level)
            _validate_entry_fields(data, db, current_user.id)
            _validate_mutable_columns(
                params.table_name,
                [key for key in data if key != "user_id"],
                "data字段",
                protected_columns=CREATE_PROTECTED_COLUMNS,
            )
            _validate_columns(params.table_name, data.keys(), "data字段")
            cols = list(data.keys())
            cols_q = ",".join(_quote_identifier(col) for col in cols)
            placeholders = ",".join(["?"] * len(cols))
            cursor.execute(
                f"INSERT INTO {table_q} ({cols_q}) VALUES ({placeholders})",
                [data[col] for col in cols],
            )
            affected_rows = cursor.rowcount
            target_scope = f"user_id = {data.get('user_id')}"
            payload = {
                **params.model_dump(),
                "after": {"id": cursor.lastrowid},
                "rollback_supported": True,
            }
        elif params.action == "update":
            _validate_mutable_columns(params.table_name, params.data.keys(), "data字段")
            if not params.data:
                raise HTTPException(status_code=400, detail="data 不能为空")
            set_clause = ", ".join(f"{_quote_identifier(key)} = ?" for key in params.data)
            clauses, where_values, scope_description = _scope_clause(
                params.table_name,
                permission_level,
                current_user,
            )
            clauses.append(f"{pk_q} = ?")
            before_snapshot = _fetch_one_row_snapshot(
                cursor,
                table_name=params.table_name,
                clauses=clauses,
                values=where_values + [params.pk_value],
            )
            if before_snapshot is None:
                raise HTTPException(status_code=404, detail="记录不存在或无权限修改")
            _validate_entry_fields(params.data, db, current_user.id, existing=before_snapshot)
            sql = f"UPDATE {table_q} SET {set_clause} WHERE {_where_sql(clauses)}"
            cursor.execute(sql, list(params.data.values()) + where_values + [params.pk_value])
            affected_rows = cursor.rowcount
            target_scope = f"{scope_description}; {params.pk_column} = {params.pk_value}"
            payload = {
                **params.model_dump(),
                "before": _select_columns(before_snapshot, params.data.keys(), params.pk_column),
                "rollback_supported": before_snapshot is not None,
            }
        else:
            clauses, where_values, scope_description = _scope_clause(
                params.table_name,
                permission_level,
                current_user,
            )
            clauses.append(f"{pk_q} = ?")
            before_snapshot = _fetch_one_row_snapshot(
                cursor,
                table_name=params.table_name,
                clauses=clauses,
                values=where_values + [params.pk_value],
            )
            if before_snapshot is None:
                raise HTTPException(status_code=404, detail="记录不存在或无权限删除")
            cursor.execute(
                f"DELETE FROM {table_q} WHERE {_where_sql(clauses)}",
                where_values + [params.pk_value],
            )
            affected_rows = cursor.rowcount
            target_scope = f"{scope_description}; {params.pk_column} = {params.pk_value}"
            payload = {
                **params.model_dump(),
                "before": before_snapshot,
                "rollback_supported": before_snapshot is not None,
            }

        _log_write(
            db,
            user=current_user,
            permission_level=permission_level,
            source="sql_editor",
            action=params.action,
            table_name=params.table_name,
            target_scope=target_scope,
            affected_rows=affected_rows,
            payload=payload,
        )
        db.commit()
        return {"status": "success", "action": params.action, "affected_rows": affected_rows}
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise_vocabulary_database_busy_if_locked(exc)
        raise HTTPException(status_code=400, detail=f"操作失败: {exc}") from exc


@router.post("/batch-mutate")
async def batch_mutate_table(
    params: BatchMutationParams,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_vocabulary_db),
):
    permission_level = _require_table_access(current_user, params.table_name, write=True, db=db)
    _require_write_action_access(permission_level, params.action)
    _validate_columns(params.table_name, [params.pk_column], "pk_column", allow_rowid=True)
    table_q = _quote_identifier(params.table_name)
    pk_q = _quote_identifier(params.pk_column)
    conn = _connection(db)
    cursor = conn.cursor()
    success_count = 0
    error_count = 0
    errors = []
    try:
        if params.action == "batch_create":
            if not params.create_data:
                raise HTTPException(status_code=400, detail="create_data 不能为空")
            records = [_sanitize_create_data(record, current_user, permission_level) for record in params.create_data]
            cols = list(records[0].keys())
            _validate_mutable_columns(
                params.table_name,
                [key for key in cols if key != "user_id"],
                "create_data字段",
                protected_columns=CREATE_PROTECTED_COLUMNS,
            )
            _validate_columns(params.table_name, cols, "create_data字段")
            cols_q = ",".join(_quote_identifier(col) for col in cols)
            placeholders = ",".join(["?"] * len(cols))
            sql = f"INSERT INTO {table_q} ({cols_q}) VALUES ({placeholders})"
            created_ids = []
            for i, record in enumerate(records):
                try:
                    _validate_entry_fields(record, db, current_user.id)
                    cursor.execute(sql, [record.get(col) for col in cols])
                    success_count += 1
                    created_ids.append(cursor.lastrowid)
                except Exception as exc:
                    error_count += 1
                    errors.append(f"第{i + 1}条记录失败: {exc}")
            target_scope = f"user_id = {current_user.id}" if permission_level == "edit" else "created rows"
            payload = {
                **params.model_dump(),
                "after": [{"id": row_id} for row_id in created_ids],
                "rollback_supported": True,
            }
        elif params.action == "batch_update":
            if not params.update_data:
                raise HTTPException(status_code=400, detail="update_data 不能为空")
            before_snapshots = []
            for i, record in enumerate(params.update_data):
                try:
                    if params.pk_column not in record:
                        raise ValueError(f"记录缺少主键字段 '{params.pk_column}'")
                    pk_value = record[params.pk_column]
                    update_fields = {key: value for key, value in record.items() if key != params.pk_column}
                    _validate_mutable_columns(params.table_name, update_fields.keys(), "update_data字段")
                    if not update_fields:
                        raise ValueError("没有需要更新的字段")
                    clauses, where_values, _ = _scope_clause(params.table_name, permission_level, current_user)
                    clauses.append(f"{pk_q} = ?")
                    before_snapshot = _fetch_one_row_snapshot(
                        cursor,
                        table_name=params.table_name,
                        clauses=clauses,
                        values=where_values + [pk_value],
                    )
                    if before_snapshot is None:
                        error_count += 1
                        errors.append(f"第{i + 1}条记录未找到或无权限 (主键={pk_value})")
                        continue
                    _validate_entry_fields(update_fields, db, current_user.id, existing=before_snapshot)
                    set_clause = ", ".join(f"{_quote_identifier(key)} = ?" for key in update_fields)
                    cursor.execute(
                        f"UPDATE {table_q} SET {set_clause} WHERE {_where_sql(clauses)}",
                        list(update_fields.values()) + where_values + [pk_value],
                    )
                    success_count += 1
                    selected = _select_columns(before_snapshot, update_fields.keys(), params.pk_column)
                    if selected is not None:
                        before_snapshots.append(selected)
                except Exception as exc:
                    error_count += 1
                    errors.append(f"第{i + 1}条记录失败: {exc}")
            target_scope = f"user_id = {current_user.id}" if permission_level == "edit" else "all rows"
            payload = {
                **params.model_dump(),
                "before": before_snapshots,
                "rollback_supported": success_count == len(before_snapshots),
            }
        else:
            if not params.delete_ids:
                raise HTTPException(status_code=400, detail="delete_ids 不能为空")
            clauses, where_values, scope_description = _scope_clause(params.table_name, permission_level, current_user)
            placeholders = ",".join(["?"] * len(params.delete_ids))
            clauses.append(f"{pk_q} IN ({placeholders})")
            cursor.execute(
                f"SELECT rowid AS __rowid__, * FROM {table_q} WHERE {_where_sql(clauses)}",
                where_values + params.delete_ids,
            )
            before_snapshots = [_row_to_dict(cursor, row) for row in cursor.fetchall()]
            cursor.execute(
                f"DELETE FROM {table_q} WHERE {_where_sql(clauses)}",
                where_values + params.delete_ids,
            )
            success_count = cursor.rowcount
            if success_count < len(params.delete_ids):
                error_count = len(params.delete_ids) - success_count
                errors.append(f"有 {error_count} 条记录未找到或无权限")
            target_scope = scope_description
            payload = {
                **params.model_dump(),
                "before": before_snapshots,
                "rollback_supported": success_count == len(before_snapshots),
            }

        _log_write(
            db,
            user=current_user,
            permission_level=permission_level,
            source="batch_mutate",
            action=params.action,
            table_name=params.table_name,
            target_scope=target_scope,
            affected_rows=success_count,
            payload=payload,
        )
        db.commit()
        return {
            "status": "completed",
            "action": params.action,
            "success_count": success_count,
            "error_count": error_count,
            "total": success_count + error_count,
            "errors": errors if errors else None,
            "message": f"批量操作完成: 成功 {success_count} 条, 失败 {error_count} 条",
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise_vocabulary_database_busy_if_locked(exc)
        raise HTTPException(status_code=400, detail=f"批量操作失败: {exc}") from exc


@router.post("/batch-replace-preview")
async def batch_replace_preview(
    params: BatchReplacePreviewParams,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_vocabulary_db),
):
    permission_level = _require_table_access(current_user, params.table_name, write=True, db=db)
    _validate_mutable_columns(params.table_name, params.columns, "columns")
    _validate_columns(params.table_name, params.filters.keys(), "filters字段")
    _validate_columns(params.table_name, params.search_columns, "search_columns")
    clauses, values, _ = _build_batch_replace_where(
        params=params,
        permission_level=permission_level,
        user=current_user,
    )
    cursor = _connection(db).execute(
        f"SELECT COUNT(*) FROM {_quote_identifier(params.table_name)} WHERE {_where_sql(clauses)}",
        values,
    )
    return {"status": "success", "total_matches": cursor.fetchone()[0]}


@router.post("/batch-replace-execute")
async def batch_replace_execute(
    params: BatchReplaceExecuteParams,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_vocabulary_db),
):
    permission_level = _require_table_access(current_user, params.table_name, write=True, db=db)
    _validate_mutable_columns(params.table_name, params.columns, "columns")
    _validate_columns(params.table_name, params.filters.keys(), "filters字段")
    _validate_columns(params.table_name, params.search_columns, "search_columns")
    clauses, where_values, scope_description = _build_batch_replace_where(
        params=params,
        permission_level=permission_level,
        user=current_user,
    )

    update_values = []
    if params.is_empty_search or params.match_mode == "exact":
        set_clause = ", ".join(f"{_quote_identifier(col)} = ?" for col in params.columns)
        update_values.extend([params.replace_text] * len(params.columns))
    else:
        set_clause = ", ".join(
            f"{_quote_identifier(col)} = REPLACE({_quote_identifier(col)}, ?, ?)"
            for col in params.columns
        )
        for _ in params.columns:
            update_values.extend([params.find_text, params.replace_text])

    conn = _connection(db)
    table_q = _quote_identifier(params.table_name)
    cursor = conn.execute(
        f"SELECT rowid AS __rowid__, * FROM {table_q} WHERE {_where_sql(clauses)}",
        where_values,
    )
    affected_rows_data = [_row_to_dict(cursor, row) for row in cursor.fetchall()]
    for row in affected_rows_data:
        simulated = dict(row)
        changed: dict[str, Any] = {}
        for col in params.columns:
            old_val = str(simulated.get(col, ""))
            if params.is_empty_search:
                if not old_val.strip():
                    new_val = params.replace_text
                else:
                    new_val = old_val
            elif params.match_mode == "exact":
                new_val = params.replace_text if old_val == params.find_text else old_val
            else:
                new_val = old_val.replace(params.find_text, params.replace_text)
            changed[col] = new_val
            simulated[col] = new_val
        _validate_entry_fields(changed, db, current_user.id, existing=row)

    try:
        cursor = conn.execute(
            f"UPDATE {table_q} SET {set_clause} WHERE {_where_sql(clauses)}",
            update_values + where_values,
        )
        affected_rows = cursor.rowcount
        _log_write(
            db,
            user=current_user,
            permission_level=permission_level,
            source="batch_replace",
            action="replace",
            table_name=params.table_name,
            target_scope=scope_description,
            affected_rows=affected_rows,
            payload={
                **params.model_dump(),
                "rollback_supported": False,
            },
        )
        db.commit()
        return {"status": "success", "affected_rows": affected_rows}
    except Exception as exc:
        db.rollback()
        raise_vocabulary_database_busy_if_locked(exc)
        raise HTTPException(status_code=400, detail=f"批量替换失败: {exc}") from exc
