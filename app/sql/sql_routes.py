import sqlite3
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.sql.choose_db import get_db_connection
from app.sql.sql_schemas import (
    MutationParams, QueryParams, DistinctQueryRequest,
    BatchMutationParams, BatchReplacePreviewParams, BatchReplaceExecuteParams
)
from app.auth.dependencies import get_current_admin_user, get_current_user
from app.logs.service.api_limiter import ApiLimiter
from app.auth.database import get_db as get_auth_db
from app.auth.models import User

router = APIRouter()


@router.post("/query")
async def query_table(
    params: QueryParams,
    user: Optional[User] = Depends(ApiLimiter),  # 自动限流和日志记录
    auth_db: Session = Depends(get_auth_db)
):
    # 限流和日志记录已由中间件和依赖注入自动处理

    # 从 params 中取出 db_key 传进去
    with get_db_connection(params.db_key, user=user, operation="read", auth_db=auth_db) as conn:
        cursor = conn.cursor()

        # 1. 基础 SQL
        sql = f"SELECT rowid, * FROM {params.table_name}"
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
                conditions.append(f"{col} IN ({placeholders})")
                values.extend(normal_values)  # 把值加入参数列表
            # 3. 构建空值的查询: (col IS NULL OR col = '')
            # SQLite 中通常把 NULL 和空字符串都视为"没填"
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


@router.get("/query/columns")
async def get_column_info(
    db_key: str,
    table_name: str,
    user: Optional[User] = Depends(ApiLimiter),  # 自动限流和日志记录
    auth_db: Session = Depends(get_auth_db)
):
    # 限流和日志记录已由中间件和依赖注入自动处理

    with get_db_connection(db_key, user=user, operation="read", auth_db=auth_db) as conn:
        # 确保可以通过列名获取数据 (如果是 sqlite3.Row 对象)
        cursor = conn.cursor()

        try:
            # 获取表结构元数据
            cursor.execute(f"PRAGMA table_info('{table_name}')")
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

@router.get("/distinct/{db_key}/{table_name}/{column}")
async def get_distinct_values(
    db_key: str,
    table_name: str,
    column: str,
    user: Optional[User] = Depends(get_current_user),
    auth_db: Session = Depends(get_auth_db)
):
    """用于前端表头筛选弹窗，获取该列所有不重复的值"""
    with get_db_connection(db_key, user=user, operation="read", auth_db=auth_db) as conn:
        # 注意安全校验 column 是否合法
        cursor = conn.execute(f"SELECT DISTINCT {column} FROM {table_name} ORDER BY {column}")
        values = [row[0] for row in cursor.fetchall() if row[0] is not None]
        return {"values": values}


@router.post("/distinct-query")
async def get_distinct_values(
    req: DistinctQueryRequest,
    user: Optional[User] = Depends(get_current_user),
    auth_db: Session = Depends(get_auth_db)
):
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


@router.post("/mutate")
async def mutate_table(
    params: MutationParams,
    current_user: User = Depends(get_current_admin_user),
    auth_db: Session = Depends(get_auth_db)
):
    """
    单个记录操作（创建/更新/删除）- 需要管理员权限

    支持的操作：
    - create: 插入单条记录
    - update: 更新单条记录（基于主键）
    - delete: 删除单条记录（基于主键）

    权限要求：管理员
    """
    # 从 params 中取出 db_key 传进去
    with get_db_connection(params.db_key, user=current_user, operation="write", auth_db=auth_db) as conn:
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
            return {"status": "success", "message": f"单个{params.action}操作成功"}
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=400, detail=str(e))


@router.post("/batch-mutate")
async def batch_mutate_table(
    params: BatchMutationParams,
    current_user: User = Depends(get_current_admin_user),
    auth_db: Session = Depends(get_auth_db)
):
    """
    批量操作（批量创建/更新/删除）- 需要管理员权限

    支持的操作：
    - batch_create: 批量插入多条记录
    - batch_update: 批量更新多条记录（每条记录必须包含主键）
    - batch_delete: 批量删除多条记录（通过主键列表）

    权限要求：管理员

    示例请求：

    1. 批量创建：
    {
        "db_key": "dialects",
        "table_name": "dialects",
        "action": "batch_create",
        "create_data": [
            {"漢字": "我", "簡稱": "北京", "聲母": "w"},
            {"漢字": "你", "簡稱": "北京", "聲母": "n"}
        ]
    }

    2. 批量更新：
    {
        "db_key": "dialects",
        "table_name": "dialects",
        "action": "batch_update",
        "pk_column": "id",
        "update_data": [
            {"id": 1, "漢字": "我", "聲母": "w"},
            {"id": 2, "漢字": "你", "聲母": "n"}
        ]
    }

    3. 批量删除：
    {
        "db_key": "dialects",
        "table_name": "dialects",
        "action": "batch_delete",
        "pk_column": "id",
        "delete_ids": [1, 2, 3, 4, 5]
    }
    """
    with get_db_connection(params.db_key, user=current_user, operation="write", auth_db=auth_db) as conn:
        cursor = conn.cursor()

        success_count = 0
        error_count = 0
        errors = []

        try:
            if params.action == "batch_create":
                if not params.create_data:
                    raise HTTPException(status_code=400, detail="create_data 不能为空")

                # 获取列名（假设所有记录的列相同）
                first_record = params.create_data[0]
                cols = list(first_record.keys())
                placeholders = ",".join(["?"] * len(cols))
                sql = f"INSERT INTO {params.table_name} ({','.join(cols)}) VALUES ({placeholders})"

                # 批量插入
                for i, record in enumerate(params.create_data):
                    try:
                        values = [record.get(col) for col in cols]
                        cursor.execute(sql, values)
                        success_count += 1
                    except Exception as e:
                        error_count += 1
                        errors.append(f"第{i+1}条记录失败: {str(e)}")

            elif params.action == "batch_update":
                if not params.update_data:
                    raise HTTPException(status_code=400, detail="update_data 不能为空")

                # 批量更新
                for i, record in enumerate(params.update_data):
                    try:
                        if params.pk_column not in record:
                            raise ValueError(f"记录缺少主键字段 '{params.pk_column}'")

                        pk_value = record[params.pk_column]
                        update_fields = {k: v for k, v in record.items() if k != params.pk_column}

                        if not update_fields:
                            raise ValueError("没有需要更新的字段")

                        set_clause = ", ".join([f"{k} = ?" for k in update_fields.keys()])
                        sql = f"UPDATE {params.table_name} SET {set_clause} WHERE {params.pk_column} = ?"

                        values = list(update_fields.values())
                        values.append(pk_value)

                        cursor.execute(sql, values)

                        if cursor.rowcount > 0:
                            success_count += 1
                        else:
                            error_count += 1
                            errors.append(f"第{i+1}条记录未找到 (主键={pk_value})")

                    except Exception as e:
                        error_count += 1
                        errors.append(f"第{i+1}条记录失败: {str(e)}")

            elif params.action == "batch_delete":
                if not params.delete_ids:
                    raise HTTPException(status_code=400, detail="delete_ids 不能为空")

                # 批量删除
                placeholders = ",".join(["?"] * len(params.delete_ids))
                sql = f"DELETE FROM {params.table_name} WHERE {params.pk_column} IN ({placeholders})"

                try:
                    cursor.execute(sql, params.delete_ids)
                    success_count = cursor.rowcount

                    # 检查是否所有ID都被删除
                    if success_count < len(params.delete_ids):
                        error_count = len(params.delete_ids) - success_count
                        errors.append(f"有 {error_count} 条记录未找到或已删除")

                except Exception as e:
                    error_count = len(params.delete_ids)
                    errors.append(f"批量删除失败: {str(e)}")

            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"不支持的批量操作: {params.action}。支持的操作: batch_create, batch_update, batch_delete"
                )

            # 提交事务
            conn.commit()

            return {
                "status": "completed",
                "action": params.action,
                "success_count": success_count,
                "error_count": error_count,
                "total": success_count + error_count,
                "errors": errors if errors else None,
                "message": f"批量操作完成: 成功 {success_count} 条, 失败 {error_count} 条"
            }

        except HTTPException:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=400, detail=f"批量操作失败: {str(e)}")


@router.post("/batch-replace-preview")
async def batch_replace_preview(
    params: BatchReplacePreviewParams,
    current_user: User = Depends(get_current_admin_user),
    auth_db: Session = Depends(get_auth_db)
):
    """
    批量替换预览统计 - 需要管理员权限

    统计全表中匹配指定条件的记录数量，不执行实际替换操作。
    用于给用户展示将要被替换的记录数量。

    权限要求：管理员
    """
    with get_db_connection(params.db_key, user=current_user, operation="read", auth_db=auth_db) as conn:
        cursor = conn.cursor()

        try:
            # 构建WHERE条件
            conditions = []
            query_params = []

            # 1. 添加筛选条件 (filters)
            if params.filters:
                for col, values in params.filters.items():
                    if not values:
                        continue

                    # 分离普通值和空值
                    has_empty = None in values
                    normal_values = [v for v in values if v is not None]
                    filter_conditions = []

                    # 处理普通值: col IN (?, ?)
                    if normal_values:
                        placeholders = ",".join(["?"] * len(normal_values))
                        filter_conditions.append(f"{col} IN ({placeholders})")
                        query_params.extend(normal_values)

                    # 处理空值: (col IS NULL OR col = '')
                    if has_empty:
                        filter_conditions.append(f"({col} IS NULL OR {col} = '')")

                    # 组合单列条件
                    if filter_conditions:
                        conditions.append(f"({' OR '.join(filter_conditions)})")

            # 2. 添加搜索条件 (search_text)
            # 在所有列中搜索（从 filters 的 keys 获取所有列名）
            if params.search_text and params.filters:
                search_columns = list(params.filters.keys())
                search_conditions = []
                like_pattern = f"%{params.search_text}%"
                for col in search_columns:
                    search_conditions.append(f"{col} LIKE ?")
                    query_params.append(like_pattern)

                if search_conditions:
                    conditions.append(f"({' OR '.join(search_conditions)})")

            # 3. 添加匹配条件（核心查找逻辑）
            match_conditions = []

            if params.is_empty_search:
                # 空值查找：col IS NULL OR col = ''
                for col in params.columns:
                    match_conditions.append(f"({col} IS NULL OR {col} = '')")
            else:
                if params.match_mode == 'exact':
                    # 完全匹配
                    for col in params.columns:
                        match_conditions.append(f"{col} = ?")
                        query_params.append(params.find_text)
                else:
                    # 包含匹配
                    for col in params.columns:
                        match_conditions.append(f"{col} LIKE ?")
                        query_params.append(f"%{params.find_text}%")

            if match_conditions:
                conditions.append(f"({' OR '.join(match_conditions)})")

            # 4. 构建完整SQL
            where_clause = ' AND '.join(conditions) if conditions else '1=1'
            sql = f"SELECT COUNT(*) FROM {params.table_name} WHERE {where_clause}"

            # 5. 执行查询
            cursor.execute(sql, query_params)
            total_matches = cursor.fetchone()[0]

            # 6. 返回结果
            return {
                "status": "success",
                "total_matches": total_matches
            }

        except Exception as e:
            raise HTTPException(status_code=400, detail=f"预览统计失败: {str(e)}")


@router.post("/batch-replace-execute")
async def batch_replace_execute(
    params: BatchReplaceExecuteParams,
    current_user: User = Depends(get_current_admin_user),
    auth_db: Session = Depends(get_auth_db)
):
    """
    批量替换执行 - 需要管理员权限

    执行全表批量替换操作，直接在数据库层面更新符合条件的记录。

    权限要求：管理员
    """
    with get_db_connection(params.db_key, user=current_user, operation="write", auth_db=auth_db) as conn:
        cursor = conn.cursor()

        try:
            # 开启事务
            cursor.execute("BEGIN TRANSACTION")

            # 构建WHERE条件（与预览API相同）
            conditions = []
            where_params = []

            # 1. 添加筛选条件
            if params.filters:
                for col, values in params.filters.items():
                    if not values:
                        continue

                    # 分离普通值和空值
                    has_empty = None in values
                    normal_values = [v for v in values if v is not None]
                    filter_conditions = []

                    # 处理普通值
                    if normal_values:
                        placeholders = ",".join(["?"] * len(normal_values))
                        filter_conditions.append(f"{col} IN ({placeholders})")
                        where_params.extend(normal_values)

                    # 处理空值
                    if has_empty:
                        filter_conditions.append(f"({col} IS NULL OR {col} = '')")

                    if filter_conditions:
                        conditions.append(f"({' OR '.join(filter_conditions)})")

            # 2. 添加搜索条件
            # 在所有列中搜索（从 filters 的 keys 获取所有列名）
            if params.search_text and params.filters:
                search_columns = list(params.filters.keys())
                search_conditions = []
                like_pattern = f"%{params.search_text}%"
                for col in search_columns:
                    search_conditions.append(f"{col} LIKE ?")
                    where_params.append(like_pattern)

                if search_conditions:
                    conditions.append(f"({' OR '.join(search_conditions)})")

            # 3. 添加匹配条件
            match_conditions = []

            if params.is_empty_search:
                # 空值查找
                for col in params.columns:
                    match_conditions.append(f"({col} IS NULL OR {col} = '')")
            else:
                if params.match_mode == 'exact':
                    # 完全匹配
                    for col in params.columns:
                        match_conditions.append(f"{col} = ?")
                        where_params.append(params.find_text)
                else:
                    # 包含匹配
                    for col in params.columns:
                        match_conditions.append(f"{col} LIKE ?")
                        where_params.append(f"%{params.find_text}%")

            if match_conditions:
                conditions.append(f"({' OR '.join(match_conditions)})")

            where_clause = ' AND '.join(conditions) if conditions else '1=1'

            # 4. 构建SET子句
            update_params = []

            if params.is_empty_search or params.match_mode == 'exact':
                # 直接替换为新值
                set_clause = ', '.join([f"{col} = ?" for col in params.columns])
                update_params.extend([params.replace_text] * len(params.columns))
            else:
                # 使用REPLACE()函数
                set_clause = ', '.join([f"{col} = REPLACE({col}, ?, ?)" for col in params.columns])
                for _ in params.columns:
                    update_params.extend([params.find_text, params.replace_text])

            # 5. 构建完整UPDATE语句
            sql = f"UPDATE {params.table_name} SET {set_clause} WHERE {where_clause}"
            all_params = update_params + where_params

            # 6. 执行更新
            cursor.execute(sql, all_params)
            affected_rows = cursor.rowcount

            # 7. 提交事务
            conn.commit()

            # 8. 返回结果
            return {
                "status": "success",
                "affected_rows": affected_rows
            }

        except Exception as e:
            # 回滚事务
            conn.rollback()
            raise HTTPException(status_code=400, detail=f"批量替换失败: {str(e)}")


