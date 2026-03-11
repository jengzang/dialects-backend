import sqlite3
import threading
from typing import Optional, Iterable

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.sql.choose_db import get_db_connection
from app.sql.sql_schemas import (
    QueryParams, DistinctQueryRequest
)
from app.service.auth.dependencies import get_current_user
from app.service.logging.dependencies import ApiLimiter
from app.service.auth.database import get_db as get_auth_db
from app.service.auth.models import User
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


@router.post("/query")
async def query_table(
    params: QueryParams,
    user: Optional[User] = Depends(ApiLimiter),  # 自动限流和日志记录
    auth_db: Session = Depends(get_auth_db)
):
    # 限流和日志记录已由中间件和依赖注入自动处理

    # 从 params 中取出 db_key 传进去
    _validate_table(params.db_key, params.table_name)
    _validate_columns(params.db_key, params.table_name, params.filters.keys(), "filters字段")
    _validate_columns(params.db_key, params.table_name, params.search_columns, "search_columns")
    if params.sort_by:
        _validate_columns(params.db_key, params.table_name, [params.sort_by], "sort_by")

    with get_db_connection(params.db_key, user=user, operation="read", auth_db=auth_db) as conn:
        cursor = conn.cursor()

        # 1. 基础 SQL
        table_q = _quote_identifier(params.table_name)
        sql = f"SELECT rowid, * FROM {table_q}"
        where_clauses = []
        values = []

        for col, val_list in params.filters.items():
            if not val_list:
                continue

            # 1. 分离"普通值"和"空值"
            # 在 Python 中，前端传来的 null 会变成 None
            has_empty = None in val_list
            # 过滤出非空的值用于 IN 查询
            normal_values = [v for v in val_list if v is not None]
            conditions = []
            # 2. 构建普通值的查询: col IN (?, ?)
            if normal_values:
                placeholders = ",".join(["?"] * len(normal_values))
                conditions.append(f"{_quote_identifier(col)} IN ({placeholders})")
                values.extend(normal_values)  # 把值加入参数列表
            # 3. 构建空值的查询: (col IS NULL OR col = '')
            # SQLite 中通常把 NULL 和空字符串都视为"没填"
            if has_empty:
                col_q = _quote_identifier(col)
                conditions.append(f"({col_q} IS NULL OR {col_q} = '')")
            # 4. 组合: (IN (...) OR IS NULL)
            if conditions:
                where_clauses.append(f"({' OR '.join(conditions)})")

        # 3. 处理全局搜索 (Search) - Requirement 4
        # 逻辑：AND (col1 LIKE %q% OR col2 LIKE %q% ...)
        if params.search_text and params.search_columns:
            search_clauses = []
            like_pattern = f"%{params.search_text}%"
            for col in params.search_columns:
                search_clauses.append(f"{_quote_identifier(col)} LIKE ?")
                values.append(like_pattern)
            if search_clauses:
                where_clauses.append(f"({' OR '.join(search_clauses)})")

        # 组合 WHERE
        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)

        # 4. 处理排序 (Sort) - Requirement 2
        if params.sort_by:
            direction = "DESC" if params.sort_desc else "ASC"
            sql += f" ORDER BY {_quote_identifier(params.sort_by)} {direction}"

        # 5. 处理分页
        offset = (params.page - 1) * params.page_size
        sql += f" LIMIT ? OFFSET ?"
        values.extend([params.page_size, offset])

        try:
            cursor.execute(sql, values)
            rows = [dict(row) for row in cursor.fetchall()]

            # 获取总条数（用于前端分页）
            # 优化：如果没有 WHERE 条件，尝试从 Redis 缓存获取总数
            if not where_clauses:
                # 无条件查询，尝试使用缓存
                cache_key = f"sql_query_count:{params.db_key}:{params.table_name}"
                total = None

                try:
                    cached_total = await redis_client.get(cache_key)
                    if cached_total is not None:
                        total = int(cached_total)
                except Exception:
                    # Redis 失败，继续执行查询
                    pass

                if total is None:
                    # 缓存未命中或 Redis 不可用，执行 COUNT 查询
                    count_sql = f"SELECT COUNT(*) FROM {table_q}"
                    cursor.execute(count_sql)
                    total = cursor.fetchone()[0]

                    # 尝试缓存结果（1 小时过期）
                    try:
                        await redis_client.setex(cache_key, 3600, str(total))
                    except Exception:
                        pass
            else:
                # 有 WHERE 条件，直接执行 COUNT 查询
                count_sql = f"SELECT COUNT(*) FROM {table_q}"
                count_values = values[:-(2)]
                count_sql += " WHERE " + " AND ".join(where_clauses)
                cursor.execute(count_sql, count_values)
                total = cursor.fetchone()[0]

            return {"data": rows, "total": total, "page": params.page}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))


@router.get("/query/columns")
async def get_column_info(
    db_key: str,
    table_name: str,
    user: Optional[User] = Depends(ApiLimiter),  # 自动限流和日志记录
    auth_db: Session = Depends(get_auth_db)
):
    # 限流和日志记录已由中间件和依赖注入自动处理

    _validate_table(db_key, table_name)
    with get_db_connection(db_key, user=user, operation="read", auth_db=auth_db) as conn:
        # 确保可以通过列名获取数据 (如果是 sqlite3.Row 对象)
        cursor = conn.cursor()

        try:
            # 获取表结构元数据
            cursor.execute(f'PRAGMA table_info("{table_name}")')
            columns = cursor.fetchall()

            # 如果没查到数据，可能是表名不存在
            if not columns:
                return {"table": table_name, "columns": [], "error": "Table not found or no columns"}

            # 直接构造列表返回
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

            return {
                "table": table_name,
                "columns": result
            }

        except Exception as e:
            raise HTTPException(status_code=400, detail=f"查询失败: {str(e)}")


@router.get("/query/count")
async def get_table_count(
    db_key: str,
    table_name: str,
    user: Optional[User] = Depends(ApiLimiter),
    auth_db: Session = Depends(get_auth_db)
):
    """
    获取指定表的总行数 - 轻量级接口

    参数:
    - db_key: 数据库标识
    - table_name: 表名

    返回:
    - count: 总行数
    """
    _validate_table(db_key, table_name)
    with get_db_connection(db_key, user=user, operation="read", auth_db=auth_db) as conn:
        cursor = conn.cursor()

        try:
            cursor.execute(f"SELECT COUNT(*) FROM {_quote_identifier(table_name)}")
            count = cursor.fetchone()[0]

            return {"count": count}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"查询失败: {str(e)}")

@router.get("/distinct/{db_key}/{table_name}/{column}")
async def get_distinct_values(
    db_key: str,
    table_name: str,
    column: str,
    user: Optional[User] = Depends(get_current_user),
    auth_db: Session = Depends(get_auth_db)
):
    """用于前端表头筛选弹窗，获取该列所有不重复的值"""
    _validate_columns(db_key, table_name, [column], "column")
    with get_db_connection(db_key, user=user, operation="read", auth_db=auth_db) as conn:
        table_q = _quote_identifier(table_name)
        col_q = _quote_identifier(column)
        cursor = conn.execute(f"SELECT DISTINCT {col_q} FROM {table_q} ORDER BY {col_q}")
        values = [row[0] for row in cursor.fetchall() if row[0] is not None]
        return {"values": values}


@router.post("/distinct-query")
async def get_distinct_values(
    req: DistinctQueryRequest,
    user: Optional[User] = Depends(get_current_user),
    auth_db: Session = Depends(get_auth_db)
):
    _validate_columns(req.db_key, req.table_name, [req.target_column], "target_column")
    _validate_columns(req.db_key, req.table_name, req.current_filters.keys(), "current_filters字段")
    _validate_columns(req.db_key, req.table_name, req.search_columns, "search_columns")

    with get_db_connection(req.db_key, user=user, operation="read", auth_db=auth_db) as conn:
        cursor = conn.cursor()

        try:
            # 1. 准备 SQL 片段容器
            where_parts = []
            params = {}  # 存放所有参数值，使用命名参数 :key

            # ==========================================
            # Part A: 处理列筛选 (Filter Logic)
            # ==========================================
            # 排除当前列
            context_filters = {k: v for k, v in req.current_filters.items() if k != req.target_column}

            for col, values in context_filters.items():
                if not values: continue

                clean_values = [v for v in values if v is not None]
                has_null = None in values
                col_conditions = []

                # 处理非空值: sqlite3 需要为列表中的每个值生成单独的占位符
                if clean_values:
                    # 生成一组参数名，例如: filter_city_0, filter_city_1
                    param_keys = []
                    for idx, val in enumerate(clean_values):
                        # 构造唯一的参数键名
                        key = f"f_{col}_{idx}"
                        params[key] = val
                        param_keys.append(f":{key}")

                    # 生成 SQL: "city" IN (:f_city_0, :f_city_1)
                    col_conditions.append(f'"{col}" IN ({", ".join(param_keys)})')

                # 处理空值
                if has_null:
                    col_conditions.append(f'"{col}" IS NULL')

                # 组合单列条件 (A OR B)
                if col_conditions:
                    where_parts.append(f"({' OR '.join(col_conditions)})")

            # ==========================================
            # Part B: 处理全局搜索 (Search Logic)
            # ==========================================
            if req.search_text and req.search_columns:
                search_parts = []
                # 统一使用一个参数值
                params["global_search"] = f"%{req.search_text}%"

                for col in req.search_columns:
                    # 生成 SQL: "col" LIKE :global_search
                    search_parts.append(f'"{col}" LIKE :global_search')

                # 组合搜索条件: (col1 LIKE %x% OR col2 LIKE %x%)
                if search_parts:
                    where_parts.append(f"({' OR '.join(search_parts)})")

            # ==========================================
            # Part C: 拼装最终 SQL
            # ==========================================
            # 注意：表名和列名使用双引号 "" 包裹以防止特殊字符报错，也是 SQLite 的标准引用方式
            table_q = _quote_identifier(req.table_name)
            target_col_q = _quote_identifier(req.target_column)
            sql = f"SELECT DISTINCT {target_col_q} FROM {table_q}"

            if where_parts:
                sql += " WHERE " + " AND ".join(where_parts)

            # 排序与限制
            sql += f" ORDER BY {target_col_q} LIMIT 1000"

            # ==========================================
            # Part D: 执行
            # ==========================================
            # print(f"SQL: {sql}")    # 调试用
            # print(f"Params: {params}") # 调试用

            cursor.execute(sql, params)
            rows = cursor.fetchall()

            # row[0] 获取第一列数据，因为是 distinct 查询只有一列
            values = [row[0] for row in rows]

            return {"values": values}

        except sqlite3.Error as e:
            raise HTTPException(status_code=400, detail=f"Database Error: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


