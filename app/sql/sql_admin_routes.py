from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.service.auth.database import get_db as get_auth_db
from app.service.auth.dependencies import get_current_admin_user
from app.service.auth.models import User
from app.sql.choose_db import get_db_connection
from app.sql.sql_routes import router, _validate_table, _validate_columns, _quote_identifier
from app.sql.sql_schemas import MutationParams, BatchMutationParams, BatchReplacePreviewParams, \
    BatchReplaceExecuteParams


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
    _validate_table(params.db_key, params.table_name)
    _validate_columns(params.db_key, params.table_name, [params.pk_column], "pk_column", allow_rowid=True)
    _validate_columns(params.db_key, params.table_name, params.data.keys(), "data字段")

    # 从 params 中取出 db_key 传进去
    with get_db_connection(params.db_key, user=current_user, operation="write", auth_db=auth_db) as conn:
        cursor = conn.cursor()
        try:
            table_q = _quote_identifier(params.table_name)
            pk_q = _quote_identifier(params.pk_column)
            if params.action == "create":
                cols = list(params.data.keys())
                cols_q = ",".join([_quote_identifier(c) for c in cols])
                placeholders = ",".join(["?"] * len(cols))
                sql = f"INSERT INTO {table_q} ({cols_q}) VALUES ({placeholders})"
                cursor.execute(sql, list(params.data.values()))

            elif params.action == "update":
                set_clause = ", ".join([f"{_quote_identifier(k)} = ?" for k in params.data.keys()])
                sql = f"UPDATE {table_q} SET {set_clause} WHERE {pk_q} = ?"
                vals = list(params.data.values())
                vals.append(params.pk_value)
                cursor.execute(sql, vals)

            elif params.action == "delete":
                sql = f"DELETE FROM {table_q} WHERE {pk_q} = ?"
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
    _validate_table(params.db_key, params.table_name)
    _validate_columns(params.db_key, params.table_name, [params.pk_column], "pk_column", allow_rowid=True)
    _validate_columns(params.db_key, params.table_name, params.create_data[0].keys() if params.create_data else [], "create_data字段")

    with get_db_connection(params.db_key, user=current_user, operation="write", auth_db=auth_db) as conn:
        cursor = conn.cursor()

        success_count = 0
        error_count = 0
        errors = []

        try:
            table_q = _quote_identifier(params.table_name)
            pk_q = _quote_identifier(params.pk_column)
            if params.action == "batch_create":
                if not params.create_data:
                    raise HTTPException(status_code=400, detail="create_data 不能为空")

                # 获取列名（假设所有记录的列相同）
                first_record = params.create_data[0]
                cols = list(first_record.keys())
                _validate_columns(params.db_key, params.table_name, cols, "create_data字段")
                placeholders = ",".join(["?"] * len(cols))
                cols_q = ",".join([_quote_identifier(c) for c in cols])
                sql = f"INSERT INTO {table_q} ({cols_q}) VALUES ({placeholders})"

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
                        _validate_columns(params.db_key, params.table_name, update_fields.keys(), "update_data字段")

                        if not update_fields:
                            raise ValueError("没有需要更新的字段")

                        set_clause = ", ".join([f"{_quote_identifier(k)} = ?" for k in update_fields.keys()])
                        sql = f"UPDATE {table_q} SET {set_clause} WHERE {pk_q} = ?"

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
                sql = f"DELETE FROM {table_q} WHERE {pk_q} IN ({placeholders})"

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
    _validate_table(params.db_key, params.table_name)
    _validate_columns(params.db_key, params.table_name, params.columns, "columns")
    _validate_columns(params.db_key, params.table_name, params.filters.keys(), "filters字段")

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
                        filter_conditions.append(f"{_quote_identifier(col)} IN ({placeholders})")
                        query_params.extend(normal_values)

                    # 处理空值: (col IS NULL OR col = '')
                    if has_empty:
                        col_q = _quote_identifier(col)
                        filter_conditions.append(f"({col_q} IS NULL OR {col_q} = '')")

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
                    search_conditions.append(f"{_quote_identifier(col)} LIKE ?")
                    query_params.append(like_pattern)

                if search_conditions:
                    conditions.append(f"({' OR '.join(search_conditions)})")

            # 3. 添加匹配条件（核心查找逻辑）
            match_conditions = []

            if params.is_empty_search:
                # 空值查找：col IS NULL OR col = ''
                for col in params.columns:
                    col_q = _quote_identifier(col)
                    match_conditions.append(f"({col_q} IS NULL OR {col_q} = '')")
            else:
                if params.match_mode == 'exact':
                    # 完全匹配
                    for col in params.columns:
                        match_conditions.append(f"{_quote_identifier(col)} = ?")
                        query_params.append(params.find_text)
                else:
                    # 包含匹配
                    for col in params.columns:
                        match_conditions.append(f"{_quote_identifier(col)} LIKE ?")
                        query_params.append(f"%{params.find_text}%")

            if match_conditions:
                conditions.append(f"({' OR '.join(match_conditions)})")

            # 4. 构建完整SQL
            where_clause = ' AND '.join(conditions) if conditions else '1=1'
            sql = f"SELECT COUNT(*) FROM {_quote_identifier(params.table_name)} WHERE {where_clause}"

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
    _validate_table(params.db_key, params.table_name)
    _validate_columns(params.db_key, params.table_name, params.columns, "columns")
    _validate_columns(params.db_key, params.table_name, params.filters.keys(), "filters字段")

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
                        filter_conditions.append(f"{_quote_identifier(col)} IN ({placeholders})")
                        where_params.extend(normal_values)

                    # 处理空值
                    if has_empty:
                        col_q = _quote_identifier(col)
                        filter_conditions.append(f"({col_q} IS NULL OR {col_q} = '')")

                    if filter_conditions:
                        conditions.append(f"({' OR '.join(filter_conditions)})")

            # 2. 添加搜索条件
            # 在所有列中搜索（从 filters 的 keys 获取所有列名）
            if params.search_text and params.filters:
                search_columns = list(params.filters.keys())
                search_conditions = []
                like_pattern = f"%{params.search_text}%"
                for col in search_columns:
                    search_conditions.append(f"{_quote_identifier(col)} LIKE ?")
                    where_params.append(like_pattern)

                if search_conditions:
                    conditions.append(f"({' OR '.join(search_conditions)})")

            # 3. 添加匹配条件
            match_conditions = []

            if params.is_empty_search:
                # 空值查找
                for col in params.columns:
                    col_q = _quote_identifier(col)
                    match_conditions.append(f"({col_q} IS NULL OR {col_q} = '')")
            else:
                if params.match_mode == 'exact':
                    # 完全匹配
                    for col in params.columns:
                        match_conditions.append(f"{_quote_identifier(col)} = ?")
                        where_params.append(params.find_text)
                else:
                    # 包含匹配
                    for col in params.columns:
                        match_conditions.append(f"{_quote_identifier(col)} LIKE ?")
                        where_params.append(f"%{params.find_text}%")

            if match_conditions:
                conditions.append(f"({' OR '.join(match_conditions)})")

            where_clause = ' AND '.join(conditions) if conditions else '1=1'

            # 4. 构建SET子句
            update_params = []

            if params.is_empty_search or params.match_mode == 'exact':
                # 直接替换为新值
                set_clause = ', '.join([f"{_quote_identifier(col)} = ?" for col in params.columns])
                update_params.extend([params.replace_text] * len(params.columns))
            else:
                # 使用REPLACE()函数
                set_clause = ', '.join([
                    f"{_quote_identifier(col)} = REPLACE({_quote_identifier(col)}, ?, ?)" for col in params.columns
                ])
                for _ in params.columns:
                    update_params.extend([params.find_text, params.replace_text])

            # 5. 构建完整UPDATE语句
            sql = f"UPDATE {_quote_identifier(params.table_name)} SET {set_clause} WHERE {where_clause}"
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
