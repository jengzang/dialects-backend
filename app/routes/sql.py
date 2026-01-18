import os
import sqlite3

from fastapi import APIRouter, HTTPException

from app.schemas.sql import MutationParams, QueryParams, DistinctQueryRequest
from common.config import DB_MAPPING

router = APIRouter()


def get_db_connection(db_key: str):
    """根据代号获取对应的数据库连接"""
    db_path = DB_MAPPING.get(db_key)

    if not db_path:
        raise HTTPException(status_code=400, detail=f"无效的数据库代号: {db_key}")

    if not os.path.exists(db_path):
        raise HTTPException(status_code=500, detail=f"数据库文件不存在: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn
@router.post("/query")
async def query_table(params: QueryParams):
    # 从 params 中取出 db_key 传进去
    conn = get_db_connection(params.db_key)
    cursor = conn.cursor()

    # 1. 基础 SQL
    sql = f"SELECT * FROM {params.table_name}"
    where_clauses = []
    values = []

    for col, val_list in params.filters.items():
        if not val_list:
            continue

        # 1. 分离“普通值”和“空值”
        # 在 Python 中，前端传来的 null 会变成 None
        has_empty = None in val_list
        # 过滤出非空的值用于 IN 查询
        normal_values = [v for v in val_list if v is not None]
        conditions = []
        # 2. 构建普通值的查询: col IN (?, ?)
        if normal_values:
            placeholders = ",".join(["?"] * len(normal_values))
            conditions.append(f"{col} IN ({placeholders})")
            values.extend(normal_values)  # 把值加入参数列表
        # 3. 构建空值的查询: (col IS NULL OR col = '')
        # SQLite 中通常把 NULL 和空字符串都视为“没填”
        if has_empty:
            conditions.append(f"({col} IS NULL OR {col} = '')")
        # 4. 组合: (IN (...) OR IS NULL)
        if conditions:
            where_clauses.append(f"({' OR '.join(conditions)})")

    # 3. 处理全局搜索 (Search) - Requirement 4
    # 逻辑：AND (col1 LIKE %q% OR col2 LIKE %q% ...)
    if params.search_text and params.search_columns:
        search_clauses = []
        like_pattern = f"%{params.search_text}%"
        for col in params.search_columns:
            search_clauses.append(f"{col} LIKE ?")
            values.append(like_pattern)
        if search_clauses:
            where_clauses.append(f"({' OR '.join(search_clauses)})")

    # 组合 WHERE
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)

    # 4. 处理排序 (Sort) - Requirement 2
    if params.sort_by:
        direction = "DESC" if params.sort_desc else "ASC"
        # 注意：这里直接拼字符串有注入风险，生产环境需校验 params.sort_by 是否在白名单中
        sql += f" ORDER BY {params.sort_by} {direction}"

    # 5. 处理分页
    offset = (params.page - 1) * params.page_size
    sql += f" LIMIT ? OFFSET ?"
    values.extend([params.page_size, offset])

    try:
        cursor.execute(sql, values)
        rows = [dict(row) for row in cursor.fetchall()]

        # 获取总条数（用于前端分页）
        count_sql = f"SELECT COUNT(*) FROM {params.table_name}"
        if where_clauses:
            # 重新构造不带 LIMIT 的 WHERE 参数
            count_values = values[:-(2)]
            count_sql += " WHERE " + " AND ".join(where_clauses)
            cursor.execute(count_sql, count_values)
        else:
            cursor.execute(count_sql)

        total = cursor.fetchone()[0]

        return {"data": rows, "total": total, "page": params.page}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()


@router.get("/distinct/{db_key}/{table_name}/{column}")
async def get_distinct_values(db_key: str, table_name: str, column: str):
    """用于前端表头筛选弹窗，获取该列所有不重复的值"""
    conn = get_db_connection(db_key)
    try:
        # 注意安全校验 column 是否合法
        cursor = conn.execute(f"SELECT DISTINCT {column} FROM {table_name} ORDER BY {column}")
        values = [row[0] for row in cursor.fetchall() if row[0] is not None]
        return {"values": values}
    finally:
        conn.close()


@router.post("/distinct-query")
async def get_distinct_values(req: DistinctQueryRequest):
    conn = get_db_connection(req.db_key)
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
        sql = f'SELECT DISTINCT "{req.target_column}" FROM "{req.table_name}"'

        if where_parts:
            sql += " WHERE " + " AND ".join(where_parts)

        # 排序与限制
        sql += f' ORDER BY "{req.target_column}" LIMIT 1000'

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
    finally:
        # 记得关闭连接
        conn.close()


@router.post("/mutate")
async def mutate_table(params: MutationParams):
    # 从 params 中取出 db_key 传进去
    conn = get_db_connection(params.db_key)
    cursor = conn.cursor()
    try:
        if params.action == "create":
            cols = list(params.data.keys())
            placeholders = ",".join(["?"] * len(cols))
            sql = f"INSERT INTO {params.table_name} ({','.join(cols)}) VALUES ({placeholders})"
            cursor.execute(sql, list(params.data.values()))

        elif params.action == "update":
            set_clause = ", ".join([f"{k} = ?" for k in params.data.keys()])
            sql = f"UPDATE {params.table_name} SET {set_clause} WHERE {params.pk_column} = ?"
            vals = list(params.data.values())
            vals.append(params.pk_value)
            cursor.execute(sql, vals)

        elif params.action == "delete":
            sql = f"DELETE FROM {params.table_name} WHERE {params.pk_column} = ?"
            cursor.execute(sql, (params.pk_value,))

        conn.commit()
        return {"status": "success"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        conn.close()

