import asyncio
import sqlite3
import threading
from typing import Optional, Iterable

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.sql.choose_db import get_db_connection
from app.sql.sql_schemas import (
    QueryParams, DistinctQueryRequest
)
from app.service.auth.core.dependencies import get_current_user
from app.service.logging.dependencies import ApiLimiter
from app.service.auth.database.connection import get_db as get_auth_db
from app.service.auth.database.models import User
from app.common.path import DB_MAPPING
from app.redis_client import redis_client

router = APIRouter()

# Schema whitelist cache: {db_key: {table_name: {col1, col2, ...}}}
_SCHEMA_CACHE = {}
_SCHEMA_LOCK = threading.Lock()


def _quote_identifier(name: str) -> str:
    """Quote validated SQL identifiers for SQLite."""
    return f'"{name}"'


def _load_schema(db_key: str, refresh: bool = False) -> dict[str, set[str]]:
    """Load table/column whitelist for a db_key."""
    with _SCHEMA_LOCK:
        if not refresh and db_key in _SCHEMA_CACHE:
            return _SCHEMA_CACHE[db_key]

        db_path = DB_MAPPING.get(db_key)
        if not db_path:
            raise HTTPException(status_code=400, detail=f"无效的数据库代号: {db_key}")

        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            tables = [
                row[0] for row in cur.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                ).fetchall()
            ]
            schema = {}
            for table in tables:
                cols = [row[1] for row in cur.execute(f'PRAGMA table_info("{table}")').fetchall()]
                schema[table] = set(cols)
            conn.close()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"加载数据库白名单失败: {str(e)}")

        _SCHEMA_CACHE[db_key] = schema
        return schema


def _validate_table(db_key: str, table_name: str) -> set[str]:
    """Validate table name against whitelist; return allowed columns."""
    schema = _load_schema(db_key)
    if table_name not in schema:
        # One refresh retry for recently changed schema.
        schema = _load_schema(db_key, refresh=True)
        if table_name not in schema:
            raise HTTPException(status_code=400, detail=f"无效的表名: {table_name}")
    return schema[table_name]


def _validate_columns(
    db_key: str,
    table_name: str,
    columns: Iterable[str],
    field_name: str = "columns",
    allow_rowid: bool = False
) -> set[str]:
    """Validate columns against table whitelist."""
    allowed = _validate_table(db_key, table_name)
    invalid = []
    for col in columns:
        if col is None:
            continue
        if allow_rowid and isinstance(col, str) and col.lower() == "rowid":
            continue
        if col not in allowed:
            invalid.append(col)
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"无效的{field_name}: {', '.join(map(str, invalid))}"
        )
    return allowed


def _build_query_sql(params: QueryParams) -> tuple[str, list, str, list[str], list, bool]:
    table_q = _quote_identifier(params.table_name)
    sql = f"SELECT rowid, * FROM {table_q}"
    where_clauses = []
    values = []

    for col, val_list in params.filters.items():
        if not val_list:
            continue
        has_empty = None in val_list
        normal_values = [v for v in val_list if v is not None]
        conditions = []
        if normal_values:
            placeholders = ",".join(["?"] * len(normal_values))
            conditions.append(f"{_quote_identifier(col)} IN ({placeholders})")
            values.extend(normal_values)
        if has_empty:
            col_q = _quote_identifier(col)
            conditions.append(f"({col_q} IS NULL OR {col_q} = '')")
        if conditions:
            where_clauses.append(f"({' OR '.join(conditions)})")

    if params.search_text and params.search_columns:
        search_clauses = []
        like_pattern = f"%{params.search_text}%"
        for col in params.search_columns:
            search_clauses.append(f"{_quote_identifier(col)} LIKE ?")
            values.append(like_pattern)
        if search_clauses:
            where_clauses.append(f"({' OR '.join(search_clauses)})")

    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)

    if params.sort_by:
        direction = "DESC" if params.sort_desc else "ASC"
        sql += f" ORDER BY {_quote_identifier(params.sort_by)} {direction}"

    offset = (params.page - 1) * params.page_size
    sql += " LIMIT ? OFFSET ?"
    page_values = values + [params.page_size, offset]
    count_values = values[:]
    return sql, page_values, table_q, where_clauses, count_values, not where_clauses


def _query_table_rows_sync(params: QueryParams, user: Optional[User], auth_db: Session) -> tuple[list[dict], str, list, bool]:
    with get_db_connection(params.db_key, user=user, operation="read", auth_db=auth_db) as conn:
        cursor = conn.cursor()
        sql, values, table_q, where_clauses, count_values, count_cacheable = _build_query_sql(params)
        cursor.execute(sql, values)
        rows = [dict(row) for row in cursor.fetchall()]
        return rows, table_q, count_values, count_cacheable


def _query_table_count_sync(params: QueryParams, user: Optional[User], auth_db: Session, table_q: str, count_values: list) -> int:
    with get_db_connection(params.db_key, user=user, operation="read", auth_db=auth_db) as conn:
        cursor = conn.cursor()
        _, _, _, where_clauses, _, _ = _build_query_sql(params)
        count_sql = f"SELECT COUNT(*) FROM {table_q}"
        if where_clauses:
            count_sql += " WHERE " + " AND ".join(where_clauses)
            cursor.execute(count_sql, count_values)
        else:
            cursor.execute(count_sql)
        return cursor.fetchone()[0]


def _get_column_info_sync(db_key: str, table_name: str, user: Optional[User], auth_db: Session) -> dict:
    with get_db_connection(db_key, user=user, operation="read", auth_db=auth_db) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(f'PRAGMA table_info("{table_name}")')
            columns = cursor.fetchall()
            if not columns:
                return {"table": table_name, "columns": [], "error": "Table not found or no columns"}
            result = [
                {
                    "name": col["name"],
                    "type": col["type"],
                    "notnull": bool(col["notnull"]),
                    "pk": bool(col["pk"]),
                    "default_value": col["dflt_value"]
                }
                for col in columns
            ]
            return {"table": table_name, "columns": result}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"查询失败: {str(e)}")


def _get_table_count_sync(
    db_key: str,
    table_name: str,
    filter_column: Optional[str],
    filter_value: Optional[str],
    user: Optional[User],
    auth_db: Session,
) -> int:
    with get_db_connection(db_key, user=user, operation="read", auth_db=auth_db) as conn:
        cursor = conn.cursor()
        table_q = _quote_identifier(table_name)
        try:
            if filter_column is not None:
                col_q = _quote_identifier(filter_column)
                if filter_value is None:
                    sql = f"SELECT COUNT(*) FROM {table_q} WHERE {col_q} IS NULL"
                    cursor.execute(sql)
                else:
                    sql = f"SELECT COUNT(*) FROM {table_q} WHERE {col_q} = ?"
                    cursor.execute(sql, (filter_value,))
            else:
                cursor.execute(f"SELECT COUNT(*) FROM {table_q}")
            return cursor.fetchone()[0]
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"查询失败: {str(e)}")


def _get_distinct_path_values_sync(db_key: str, table_name: str, column: str, user: Optional[User], auth_db: Session) -> list:
    with get_db_connection(db_key, user=user, operation="read", auth_db=auth_db) as conn:
        table_q = _quote_identifier(table_name)
        col_q = _quote_identifier(column)
        cursor = conn.execute(f"SELECT DISTINCT {col_q} FROM {table_q} ORDER BY {col_q}")
        return [row[0] for row in cursor.fetchall() if row[0] is not None]


def _get_distinct_query_values_sync(req: DistinctQueryRequest, user: Optional[User], auth_db: Session) -> list:
    with get_db_connection(req.db_key, user=user, operation="read", auth_db=auth_db) as conn:
        cursor = conn.cursor()
        try:
            where_parts = []
            params = {}
            context_filters = {k: v for k, v in req.current_filters.items() if k != req.target_column}
            for col_idx, (col, values) in enumerate(context_filters.items()):
                if not values:
                    continue
                clean_values = [v for v in values if v is not None]
                has_null = None in values
                col_conditions = []
                if clean_values:
                    param_keys = []
                    for idx, val in enumerate(clean_values):
                        key = f"f_{col_idx}_{idx}"
                        params[key] = val
                        param_keys.append(f":{key}")
                    col_conditions.append(f'{_quote_identifier(col)} IN ({", ".join(param_keys)})')
                if has_null:
                    col_conditions.append(f'{_quote_identifier(col)} IS NULL')
                if col_conditions:
                    where_parts.append(f"({' OR '.join(col_conditions)})")

            if req.search_text and req.search_columns:
                search_parts = []
                params["global_search"] = f"%{req.search_text}%"
                for col in req.search_columns:
                    search_parts.append(f'{_quote_identifier(col)} LIKE :global_search')
                if search_parts:
                    where_parts.append(f"({' OR '.join(search_parts)})")

            table_q = _quote_identifier(req.table_name)
            target_col_q = _quote_identifier(req.target_column)
            sql = f"SELECT DISTINCT {target_col_q} FROM {table_q}"
            if where_parts:
                sql += " WHERE " + " AND ".join(where_parts)
            sql += f" ORDER BY {target_col_q} LIMIT 1000"
            cursor.execute(sql, params)
            return [row[0] for row in cursor.fetchall()]
        except sqlite3.Error as e:
            raise HTTPException(status_code=400, detail=f"Database Error: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@router.post("/query")
async def query_table(
    params: QueryParams,
    user: Optional[User] = Depends(ApiLimiter),  # 自动限流和日志记录
    auth_db: Session = Depends(get_auth_db)
):
    await asyncio.to_thread(_validate_table, params.db_key, params.table_name)
    await asyncio.to_thread(_validate_columns, params.db_key, params.table_name, params.filters.keys(), "filters字段")
    await asyncio.to_thread(_validate_columns, params.db_key, params.table_name, params.search_columns, "search_columns")
    if params.sort_by:
        await asyncio.to_thread(_validate_columns, params.db_key, params.table_name, [params.sort_by], "sort_by")

    try:
        rows, table_q, count_values, count_cacheable = await asyncio.to_thread(
            _query_table_rows_sync,
            params,
            user,
            None,
        )

        total = None
        if count_cacheable:
            cache_key = f"sql_query_count:{params.db_key}:{params.table_name}"
            try:
                cached_total = await redis_client.get(cache_key)
                if cached_total is not None:
                    total = int(cached_total)
            except Exception:
                pass

        if total is None:
            total = await asyncio.to_thread(
                _query_table_count_sync,
                params,
                user,
                None,
                table_q,
                count_values,
            )
            if count_cacheable:
                try:
                    await redis_client.setex(cache_key, 3600, str(total))
                except Exception:
                    pass

        return {"data": rows, "total": total, "page": params.page}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/query/columns")
async def get_column_info(
    db_key: str,
    table_name: str,
    user: Optional[User] = Depends(ApiLimiter),  # 自动限流和日志记录
    auth_db: Session = Depends(get_auth_db)
):
    await asyncio.to_thread(_validate_table, db_key, table_name)
    return await asyncio.to_thread(_get_column_info_sync, db_key, table_name, user, None)


@router.get("/query/count")
async def get_table_count(
    db_key: str,
    table_name: str,
    filter_column: Optional[str] = None,
    filter_value: Optional[str] = None,
    user: Optional[User] = Depends(ApiLimiter),
    auth_db: Session = Depends(get_auth_db)
):
    """获取指定表的行数 - 轻量级接口"""
    await asyncio.to_thread(_validate_table, db_key, table_name)
    if filter_column is not None:
        await asyncio.to_thread(_validate_columns, db_key, table_name, [filter_column], "filter_column")

    cache_key = f"sql_count:{db_key}:{table_name}"
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
        db_key,
        table_name,
        filter_column,
        filter_value,
        user,
        None,
    )

    try:
        await redis_client.setex(cache_key, 3600, str(count))
    except Exception:
        pass

    return {"count": count}


@router.get("/distinct/{db_key}/{table_name}/{column}")
async def get_distinct_values(
    db_key: str,
    table_name: str,
    column: str,
    user: Optional[User] = Depends(get_current_user),
    auth_db: Session = Depends(get_auth_db)
):
    """用于前端表头筛选弹窗，获取该列所有不重复的值"""
    await asyncio.to_thread(_validate_columns, db_key, table_name, [column], "column")
    values = await asyncio.to_thread(_get_distinct_path_values_sync, db_key, table_name, column, user, None)
    return {"values": values}


@router.post("/distinct-query")
async def get_distinct_values(
    req: DistinctQueryRequest,
    user: Optional[User] = Depends(get_current_user),
    auth_db: Session = Depends(get_auth_db)
):
    await asyncio.to_thread(_validate_columns, req.db_key, req.table_name, [req.target_column], "target_column")
    await asyncio.to_thread(_validate_columns, req.db_key, req.table_name, req.current_filters.keys(), "current_filters字段")
    await asyncio.to_thread(_validate_columns, req.db_key, req.table_name, req.search_columns, "search_columns")
    values = await asyncio.to_thread(_get_distinct_query_values_sync, req, user, None)
    return {"values": values}
