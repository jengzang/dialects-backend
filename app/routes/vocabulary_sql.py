from collections.abc import Iterable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

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
from app.service.vocabulary.database import get_db as get_vocabulary_db
from app.service.vocabulary.logging import record_vocabulary_log
from app.service.vocabulary.permissions import get_effective_permission_level


router = APIRouter()

EDITABLE_TABLES = {"vocabulary_entries", "vocabulary_locations"}
MANAGE_ONLY_READ_TABLES = {"vocabulary_logs"}
ALLOWED_TABLES = EDITABLE_TABLES | MANAGE_ONLY_READ_TABLES
OWNED_TABLES = {"vocabulary_entries", "vocabulary_locations"}
WRITE_PROTECTED_COLUMNS = {"id", "user_id"}


def _quote_identifier(name: str) -> str:
    return f'"{name}"'


def _connection(db: Session):
    conn = db.connection().connection
    conn.row_factory = None
    return conn


def _load_columns(db: Session, table_name: str) -> set[str]:
    rows = _connection(db).execute(f'PRAGMA table_info("{table_name}")').fetchall()
    return {row[1] for row in rows}


def _require_table_access(
    db: Session,
    user: User,
    table_name: str,
    *,
    write: bool = False,
) -> str:
    if table_name not in ALLOWED_TABLES:
        raise HTTPException(status_code=400, detail=f"无效的词表表名: {table_name}")

    permission_level = get_effective_permission_level(db, user)
    if table_name in MANAGE_ONLY_READ_TABLES and permission_level != "manage":
        raise HTTPException(status_code=403, detail="只有 manage 用户可以访问该表")
    if write and table_name not in EDITABLE_TABLES:
        raise HTTPException(status_code=403, detail="该表不允许通过词表 SQL 接口编辑")
    return permission_level


def _validate_columns(
    db: Session,
    table_name: str,
    columns: Iterable[str],
    field_name: str,
    *,
    allow_rowid: bool = False,
) -> set[str]:
    allowed = _load_columns(db, table_name)
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
    db: Session,
    table_name: str,
    columns: Iterable[str],
    field_name: str,
) -> None:
    _validate_columns(db, table_name, columns, field_name)
    protected = [col for col in columns if col in WRITE_PROTECTED_COLUMNS]
    if protected:
        raise HTTPException(status_code=400, detail=f"不允许修改字段: {', '.join(protected)}")


def _scope_clause(table_name: str, permission_level: str, user: User) -> tuple[list[str], list[Any], str]:
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
    user: User,
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
    return {description[0]: row[index] for index, description in enumerate(cursor.description)}


def _sanitize_create_data(record: dict[str, Any], user: User, permission_level: str) -> dict[str, Any]:
    data = dict(record)
    data.pop("id", None)
    data["user_id"] = user.id
    return data


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


@router.post("/query")
async def query_table(
    params: QueryParams,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_vocabulary_db),
):
    permission_level = _require_table_access(db, current_user, params.table_name)
    _validate_columns(db, params.table_name, params.filters.keys(), "filters字段")
    _validate_columns(db, params.table_name, params.search_columns, "search_columns")
    if params.sort_by:
        _validate_columns(db, params.table_name, [params.sort_by], "sort_by")

    clauses, values, _ = _build_query_where(
        table_name=params.table_name,
        permission_level=permission_level,
        user=current_user,
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
    conn = _connection(db)
    cursor = conn.cursor()
    try:
        cursor.execute(
            f"SELECT rowid, * FROM {table_q} WHERE {where_clause}{order_clause} LIMIT ? OFFSET ?",
            values + [params.page_size, offset],
        )
        rows = [_row_to_dict(cursor, row) for row in cursor.fetchall()]
        cursor.execute(f"SELECT COUNT(*) FROM {table_q} WHERE {where_clause}", values)
        total = cursor.fetchone()[0]
        return {"data": rows, "total": total, "page": params.page}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"查询失败: {exc}") from exc


@router.get("/query/columns")
async def get_column_info(
    table_name: str = "vocabulary_entries",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_vocabulary_db),
):
    _require_table_access(db, current_user, table_name)
    rows = _connection(db).execute(f'PRAGMA table_info("{table_name}")').fetchall()
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


@router.get("/query/count")
async def get_table_count(
    table_name: str = "vocabulary_entries",
    filter_column: str | None = None,
    filter_value: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_vocabulary_db),
):
    permission_level = _require_table_access(db, current_user, table_name)
    filters = {}
    if filter_column is not None:
        _validate_columns(db, table_name, [filter_column], "filter_column")
        filters[filter_column] = [filter_value]
    clauses, values, _ = _build_query_where(
        table_name=table_name,
        permission_level=permission_level,
        user=current_user,
        filters=filters,
        search_text=None,
        search_columns=[],
    )
    cursor = _connection(db).execute(
        f"SELECT COUNT(*) FROM {_quote_identifier(table_name)} WHERE {_where_sql(clauses)}",
        values,
    )
    return {"count": cursor.fetchone()[0]}


@router.get("/distinct/{table_name}/{column}")
async def get_distinct_path_values(
    table_name: str,
    column: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_vocabulary_db),
):
    permission_level = _require_table_access(db, current_user, table_name)
    _validate_columns(db, table_name, [column], "column")
    clauses, values, _ = _build_query_where(
        table_name=table_name,
        permission_level=permission_level,
        user=current_user,
        filters={},
        search_text=None,
        search_columns=[],
    )
    col_q = _quote_identifier(column)
    cursor = _connection(db).execute(
        f"SELECT DISTINCT {col_q} FROM {_quote_identifier(table_name)} "
        f"WHERE {_where_sql(clauses)} ORDER BY {col_q} LIMIT 1000",
        values,
    )
    return {"values": [row[0] for row in cursor.fetchall() if row[0] is not None]}


@router.post("/distinct-query")
async def get_distinct_query_values(
    req: DistinctQueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_vocabulary_db),
):
    permission_level = _require_table_access(db, current_user, req.table_name)
    _validate_columns(db, req.table_name, [req.target_column], "target_column")
    _validate_columns(db, req.table_name, req.current_filters.keys(), "current_filters字段")
    _validate_columns(db, req.table_name, req.search_columns, "search_columns")
    context_filters = {k: v for k, v in req.current_filters.items() if k != req.target_column}
    clauses, values, _ = _build_query_where(
        table_name=req.table_name,
        permission_level=permission_level,
        user=current_user,
        filters=context_filters,
        search_text=req.search_text,
        search_columns=req.search_columns,
    )
    target_col_q = _quote_identifier(req.target_column)
    cursor = _connection(db).execute(
        f"SELECT DISTINCT {target_col_q} FROM {_quote_identifier(req.table_name)} "
        f"WHERE {_where_sql(clauses)} ORDER BY {target_col_q} LIMIT 1000",
        values,
    )
    return {"values": [row[0] for row in cursor.fetchall()]}


@router.post("/mutate")
async def mutate_table(
    params: MutationParams,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_vocabulary_db),
):
    permission_level = _require_table_access(db, current_user, params.table_name, write=True)
    _validate_columns(db, params.table_name, [params.pk_column], "pk_column", allow_rowid=True)
    table_q = _quote_identifier(params.table_name)
    pk_q = _quote_identifier(params.pk_column)
    conn = _connection(db)
    cursor = conn.cursor()
    try:
        if params.action == "create":
            data = _sanitize_create_data(params.data, current_user, permission_level)
            _validate_mutable_columns(db, params.table_name, [key for key in data if key != "user_id"], "data字段")
            _validate_columns(db, params.table_name, data.keys(), "data字段")
            cols = list(data.keys())
            cols_q = ",".join(_quote_identifier(col) for col in cols)
            placeholders = ",".join(["?"] * len(cols))
            cursor.execute(
                f"INSERT INTO {table_q} ({cols_q}) VALUES ({placeholders})",
                [data[col] for col in cols],
            )
            affected_rows = cursor.rowcount
            target_scope = f"user_id = {data.get('user_id')}"
        elif params.action == "update":
            _validate_mutable_columns(db, params.table_name, params.data.keys(), "data字段")
            if not params.data:
                raise HTTPException(status_code=400, detail="data 不能为空")
            set_clause = ", ".join(f"{_quote_identifier(key)} = ?" for key in params.data)
            clauses, where_values, scope_description = _scope_clause(
                params.table_name,
                permission_level,
                current_user,
            )
            clauses.append(f"{pk_q} = ?")
            sql = f"UPDATE {table_q} SET {set_clause} WHERE {_where_sql(clauses)}"
            cursor.execute(sql, list(params.data.values()) + where_values + [params.pk_value])
            affected_rows = cursor.rowcount
            target_scope = f"{scope_description}; {params.pk_column} = {params.pk_value}"
        else:
            clauses, where_values, scope_description = _scope_clause(
                params.table_name,
                permission_level,
                current_user,
            )
            clauses.append(f"{pk_q} = ?")
            cursor.execute(
                f"DELETE FROM {table_q} WHERE {_where_sql(clauses)}",
                where_values + [params.pk_value],
            )
            affected_rows = cursor.rowcount
            target_scope = f"{scope_description}; {params.pk_column} = {params.pk_value}"

        _log_write(
            db,
            user=current_user,
            permission_level=permission_level,
            source="sql_editor",
            action=params.action,
            table_name=params.table_name,
            target_scope=target_scope,
            affected_rows=affected_rows,
            payload=params.model_dump(),
        )
        db.commit()
        return {"status": "success", "action": params.action, "affected_rows": affected_rows}
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"操作失败: {exc}") from exc


@router.post("/batch-mutate")
async def batch_mutate_table(
    params: BatchMutationParams,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_vocabulary_db),
):
    permission_level = _require_table_access(db, current_user, params.table_name, write=True)
    _validate_columns(db, params.table_name, [params.pk_column], "pk_column", allow_rowid=True)
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
            _validate_mutable_columns(db, params.table_name, [key for key in cols if key != "user_id"], "create_data字段")
            _validate_columns(db, params.table_name, cols, "create_data字段")
            cols_q = ",".join(_quote_identifier(col) for col in cols)
            placeholders = ",".join(["?"] * len(cols))
            sql = f"INSERT INTO {table_q} ({cols_q}) VALUES ({placeholders})"
            for i, record in enumerate(records):
                try:
                    cursor.execute(sql, [record.get(col) for col in cols])
                    success_count += 1
                except Exception as exc:
                    error_count += 1
                    errors.append(f"第{i + 1}条记录失败: {exc}")
            target_scope = f"user_id = {current_user.id}" if permission_level == "edit" else "created rows"
        elif params.action == "batch_update":
            if not params.update_data:
                raise HTTPException(status_code=400, detail="update_data 不能为空")
            for i, record in enumerate(params.update_data):
                try:
                    if params.pk_column not in record:
                        raise ValueError(f"记录缺少主键字段 '{params.pk_column}'")
                    pk_value = record[params.pk_column]
                    update_fields = {key: value for key, value in record.items() if key != params.pk_column}
                    _validate_mutable_columns(db, params.table_name, update_fields.keys(), "update_data字段")
                    if not update_fields:
                        raise ValueError("没有需要更新的字段")
                    clauses, where_values, _ = _scope_clause(params.table_name, permission_level, current_user)
                    clauses.append(f"{pk_q} = ?")
                    set_clause = ", ".join(f"{_quote_identifier(key)} = ?" for key in update_fields)
                    cursor.execute(
                        f"UPDATE {table_q} SET {set_clause} WHERE {_where_sql(clauses)}",
                        list(update_fields.values()) + where_values + [pk_value],
                    )
                    if cursor.rowcount > 0:
                        success_count += 1
                    else:
                        error_count += 1
                        errors.append(f"第{i + 1}条记录未找到或无权限 (主键={pk_value})")
                except Exception as exc:
                    error_count += 1
                    errors.append(f"第{i + 1}条记录失败: {exc}")
            target_scope = f"user_id = {current_user.id}" if permission_level == "edit" else "all rows"
        else:
            if not params.delete_ids:
                raise HTTPException(status_code=400, detail="delete_ids 不能为空")
            clauses, where_values, scope_description = _scope_clause(params.table_name, permission_level, current_user)
            placeholders = ",".join(["?"] * len(params.delete_ids))
            clauses.append(f"{pk_q} IN ({placeholders})")
            cursor.execute(
                f"DELETE FROM {table_q} WHERE {_where_sql(clauses)}",
                where_values + params.delete_ids,
            )
            success_count = cursor.rowcount
            if success_count < len(params.delete_ids):
                error_count = len(params.delete_ids) - success_count
                errors.append(f"有 {error_count} 条记录未找到或无权限")
            target_scope = scope_description

        _log_write(
            db,
            user=current_user,
            permission_level=permission_level,
            source="batch_mutate",
            action=params.action,
            table_name=params.table_name,
            target_scope=target_scope,
            affected_rows=success_count,
            payload=params.model_dump(),
        )
        db.commit()
        return {
            "status": "completed",
            "action": params.action,
            "success_count": success_count,
            "error_count": error_count,
            "total": success_count + error_count,
            "errors": errors if errors else None,
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"批量操作失败: {exc}") from exc


@router.post("/batch-replace-preview")
async def batch_replace_preview(
    params: BatchReplacePreviewParams,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_vocabulary_db),
):
    permission_level = _require_table_access(db, current_user, params.table_name, write=True)
    _validate_mutable_columns(db, params.table_name, params.columns, "columns")
    _validate_columns(db, params.table_name, params.filters.keys(), "filters字段")
    _validate_columns(db, params.table_name, params.search_columns, "search_columns")
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
    permission_level = _require_table_access(db, current_user, params.table_name, write=True)
    _validate_mutable_columns(db, params.table_name, params.columns, "columns")
    _validate_columns(db, params.table_name, params.filters.keys(), "filters字段")
    _validate_columns(db, params.table_name, params.search_columns, "search_columns")
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

    try:
        cursor = _connection(db).execute(
            f"UPDATE {_quote_identifier(params.table_name)} SET {set_clause} WHERE {_where_sql(clauses)}",
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
            payload=params.model_dump(),
        )
        db.commit()
        return {"status": "success", "affected_rows": affected_rows}
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"批量替换失败: {exc}") from exc
