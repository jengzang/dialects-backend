"""
树形结构API - 优化版本

性能优化：
1. 使用 DISTINCT 减少数据量
2. 只查询必要的列
3. 树构建使用 O(n*m) 时间复杂度，m为层级数（通常≤5）
4. 懒加载模式每次查询都使用索引（等值查询）
5. 建议在层级列上创建索引以提升查询速度

建议的数据库索引：
CREATE INDEX idx_level_0 ON 广东省自然村(市级);
CREATE INDEX idx_level_1 ON 广东省自然村(区县级);
CREATE INDEX idx_level_2 ON 广东省自然村(乡镇级);
CREATE INDEX idx_level_3 ON 广东省自然村(行政村);
"""

from fastapi import APIRouter, HTTPException
from typing import List, Optional, Dict, Any

from app.sql.choose_db import get_db_connection
from app.sql.sql_schemas import FullTreeParams, LazyTreeParams

router = APIRouter()


def validate_columns(level_columns: List[int], data_columns: List[int], all_column_names: List[str]):
    """验证列号有效性（同时检查层级列和数据列）"""
    # 合并检查所有涉及的列
    all_indices = level_columns + data_columns

    if not level_columns:
        raise HTTPException(status_code=400, detail="level_columns 不能为空")

    if not all_indices:
        return

    min_col = min(all_indices)
    max_col = max(all_indices)

    if min_col < 0:
        raise HTTPException(status_code=400, detail="列号不能为负数（从0开始）")

    if max_col >= len(all_column_names):
        raise HTTPException(
            status_code=400,
            detail=f"列号 {max_col} 超出范围（共{len(all_column_names)}列，从0开始）"
        )

def build_filter_conditions(
        filters: Optional[Dict[int, List[str]]],
        all_column_names: List[str]
) -> tuple:
    """
    构建WHERE过滤条件

    返回: (where_clauses列表, values列表)
    """
    where_clauses = []
    values = []

    if not filters:
        return where_clauses, values

    for col_index, val_list in filters.items():
        # 验证列号和值列表
        if col_index < 0 or col_index >= len(all_column_names) or not val_list:
            continue

        col_name = all_column_names[col_index]

        # 分离普通值和空值
        has_empty = None in val_list
        normal_values = [v for v in val_list if v is not None]

        conditions = []

        # 处理普通值：使用 IN 查询
        if normal_values:
            placeholders = ",".join(["?"] * len(normal_values))
            conditions.append(f"{col_name} IN ({placeholders})")
            values.extend(normal_values)

        # 处理空值
        if has_empty:
            conditions.append(f"({col_name} IS NULL OR {col_name} = '')")

        # 组合条件
        if conditions:
            where_clauses.append(f"({' OR '.join(conditions)})")

    return where_clauses, values


def build_tree_structure(rows: List[Dict], level_names: List[str], data_names: List[str] = None) -> Dict[str, Any]:
    """
    构建树形结构（优化版本）

    时间复杂度: O(n * m)，其中 n 是行数，m 是层级数（通常 m ≤ 5）
    空间复杂度: O(n)

    输入: [
      {'市级': '广州', '区县级': '天河', ..., '自然村': '村1'},
      {'市级': '广州', '区县级': '天河', ..., '自然村': '村2'},
    ]
    输出: {
      '广州': {
        '天河': {
          ...: {
            'XX村': ['村1', '村2']  # 最后一层是数组
          }
        }
      }
    }
    """
    if not rows or not level_names:
        return {}

    tree = {}
    has_data = bool(data_names)  # 标记是否需要提取数据
    PLACEHOLDER = "(空)"
    # 遍历每一行，构建树结构
    for row in rows:
        current = tree
        # path_complete = True

        # 1. 构建目录层级
        for i in range(len(level_names) - 1):
            col_name = level_names[i]
            original_value = row.get(col_name)

            # 处理空值逻辑
            if original_value is None or str(original_value).strip() == "":
                # 方案：使用占位符
                value = PLACEHOLDER
                # 进阶方案：甚至可以带上列名，比如 "未分类(区县级)"
                # value = f"未分类({col_name})"
            else:
                value = str(original_value).strip()

            if value not in current:
                current[value] = {}
            current = current[value]

        # 2. 处理叶子节点 (最后一层)
        last_col_name = level_names[-1]
        last_original_value = row.get(last_col_name)

        # 如果连叶子节点的名字都是空的，那确实该丢弃了
        # 或者你也给它一个 "未命名节点" 的名字
        if last_original_value is None or str(last_original_value).strip() == "":
            continue

        leaf_name = str(last_original_value).strip()

        # === 分支逻辑：有数据提取 vs 无数据提取 ===
        if has_data:
            # 初始化
            if leaf_name not in current:
                current[leaf_name] = {d_name: [] for d_name in data_names}

            # 追加数据（保留重复，保留空值）
            for d_name in data_names:
                val = row.get(d_name)
                # 直接 append，不做 None 判断，确保 index 对齐
                current[leaf_name][d_name].append(val)

        else:
            # 旧模式（仅结构）
            if '_items' not in current:
                current['_items'] = []
            if leaf_name not in current['_items']:
                current['_items'].append(leaf_name)

    # 清理树结构：将 '_items' 转换为直接的数组
    def clean_tree(node: Any) -> Any:
        """
        清理树结构：
        - 如果节点只有 '_items'，返回数组
        - 否则递归处理子节点
        """
        if not isinstance(node, dict):
            return node

        # 如果有 '_items' 键
        if '_items' in node:
            # 对数组排序
            items = sorted(node['_items'])

            # 检查是否还有其他键
            other_keys = {k for k in node.keys() if k != '_items'}

            if not other_keys:
                # 只有 '_items'，直接返回数组
                return items
            else:
                # 有其他子节点（这种情况不应该发生，但为了兼容保留）
                result = {}
                for key, value in node.items():
                    if key == '_items':
                        result['_items'] = items
                    else:
                        cleaned = clean_tree(value)
                        if cleaned:
                            result[key] = cleaned
                return result
        else:
            # 没有 '_items'，递归处理所有子节点
            result = {}
            for key, value in node.items():
                cleaned = clean_tree(value)
                # 只保留非空节点
                if cleaned is not None and cleaned != {} and cleaned != []:
                    result[key] = cleaned
            return result

    if has_data:
        return tree

        # 如果是旧模式，执行原来的压缩逻辑
    return clean_tree(tree)


# ========== API 1: 完整树模式 ==========
@router.post("/tree/full")
async def get_full_tree(params: FullTreeParams):
    """
    获取完整树形结构

    适用场景：
    - 数据量较小（<1万条去重后的记录）
    - 已通过filters过滤大部分数据
    - 需要完整的树结构进行前端展示和搜索

    参数：
    - db_key: 数据库代号
    - table_name: 表名
    - level_columns: 层级列号，从0开始，例如 [0, 1, 2, 3, 4]
    - data_columns: 信息列號
    - filters: 可选过滤条件，{列号: [值列表]}

    返回：
    {
      "tree": {...},           # 树形结构
      "total_nodes": 12345,    # 去重后的节点总数
      "levels": 5              # 层级数
    }
    """
    with get_db_connection(params.db_key) as conn:
        cursor = conn.cursor()

        try:
            # 获取表结构
            cursor.execute(f"PRAGMA table_info({params.table_name})")
            columns_info = cursor.fetchall()

            if not columns_info:
                raise HTTPException(status_code=400, detail=f"表不存在: {params.table_name}")

            all_column_names = [col[1] for col in columns_info]

            # 1. 验证所有列
            validate_columns(params.level_columns, params.data_columns, all_column_names)

            # 2. 获取列名列表
            level_col_names = [all_column_names[i] for i in params.level_columns]
            data_col_names = [all_column_names[i] for i in params.data_columns]

            # 合并查询列：层级列 + 数据列
            # 注意：这里继续使用 DISTINCT。
            # 如果 row1 和 row2 层级相同但数据不同，DISTINCT 会保留两者，
            # build_tree_structure 会负责把它们聚合到同一个叶子节点下。
            select_cols = level_col_names + data_col_names
            # 去重选择，防止完全重复的行
            sql = f"SELECT DISTINCT {', '.join(select_cols)} FROM {params.table_name}"

            # ... (过滤条件逻辑 build_filter_conditions 不变) ...
            where_clauses, values = build_filter_conditions(params.filters, all_column_names)
            if where_clauses:
                sql += " WHERE " + " AND ".join(where_clauses)

            # 排序：只按层级列排序即可，保证树构建顺序
            order_by = ", ".join([f"{name} ASC" for name in level_col_names])
            sql += f" ORDER BY {order_by}"

            # 执行查询
            cursor.execute(sql, values)
            rows = [dict(row) for row in cursor.fetchall()]

            # 3. 传入数据列名进行构建
            tree = build_tree_structure(rows, level_col_names, data_col_names)

            return {
                "tree": tree,
                "total_nodes": len(rows),
                "levels": len(params.level_columns)
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"构建树失败: {str(e)}")


# ========== API 2: 懒加载模式 ==========
@router.post("/tree/lazy")
async def get_tree_children(params: LazyTreeParams):
    """
    懒加载模式：获取指定路径下的子节点

    适用场景：
    - 数据量大（>1万条）
    - 按需加载，减少初始加载时间
    - 只需要展示用户点击的部分

    参数：
    - db_key: 数据库代号
    - table_name: 表名
    - level_columns: 层级列号，从0开始
    - parent_path: 父节点路径，None或[]表示获取第一层
    - filters: 可选过滤条件

    返回（第一层）：
    {
      "level": 0,
      "children": ["广州", "深圳", ...],
      "total": 21
    }

    返回（子节点）：
    {
      "level": 2,
      "parent_path": ["广州", "天河区"],
      "children": ["石牌街道", ...],
      "total": 15
    }
    """
    with get_db_connection(params.db_key) as conn:
        cursor = conn.cursor()

        try:
            # 获取表结构
            cursor.execute(f"PRAGMA table_info({params.table_name})")
            columns_info = cursor.fetchall()

            if not columns_info:
                raise HTTPException(status_code=400, detail=f"表不存在: {params.table_name}")

            all_column_names = [col[1] for col in columns_info]

            # 验证列号
            validate_columns(params.level_columns, [], all_column_names)

            # 确定要查询的层级
            parent_path = params.parent_path or []
            target_level = len(parent_path)

            # 检查是否超出最大层级
            if target_level >= len(params.level_columns):
                return {
                    "level": target_level,
                    "parent_path": parent_path,
                    "children": [],
                    "total": 0
                }

            # 确定目标列
            target_col_index = params.level_columns[target_level]
            target_col_name = all_column_names[target_col_index]

            # 构建SQL：只查询目标列的唯一值
            sql = f"SELECT DISTINCT {target_col_name} FROM {params.table_name}"

            where_clauses = []
            values = []

            # 添加父路径的WHERE条件
            for i, parent_value in enumerate(parent_path):
                col_index = params.level_columns[i]
                col_name = all_column_names[col_index]
                where_clauses.append(f"{col_name} = ?")
                values.append(parent_value)

            # 添加全局过滤条件
            filter_clauses, filter_values = build_filter_conditions(params.filters, all_column_names)
            where_clauses.extend(filter_clauses)
            values.extend(filter_values)

            # 组合WHERE子句
            if where_clauses:
                sql += " WHERE " + " AND ".join(where_clauses)

            # 排序
            sql += f" ORDER BY {target_col_name} ASC"

            # 执行查询
            cursor.execute(sql, values)

            # 提取结果并过滤空值
            children = []
            seen = set()  # 去重
            for row in cursor.fetchall():
                value = (row[0] or '').strip()
                if value and value not in seen:
                    children.append(value)
                    seen.add(value)

            return {
                "level": target_level,
                "parent_path": parent_path if parent_path else None,
                "children": children,
                "total": len(children)
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"获取子节点失败: {str(e)}")

# ========== 使用示例 ==========
#
# 【完整树模式】适合：已过滤的数据或数据量小
#
# 示例1：只查询广州市的完整树
# POST /api/tree/full
# {
#   "db_key": "village",
#   "table_name": "广东省自然村",
#   "level_columns": [0, 1, 2, 3, 4],  # 市级、区县级、乡镇级、行政村、自然村
#   "filters": {
#     0: ["广州市"]  # 只查广州，数据量从20万降到几万
#   }
# }
# 性能：DISTINCT后约1-2万条，构建树约100-300ms
#
# 示例2：查询多个城市
# POST /api/tree/full
# {
#   "db_key": "village",
#   "table_name": "广东省自然村",
#   "level_columns": [0, 1, 2, 3, 4],
#   "filters": {
#     0: ["广州", "深圳", "珠海"]
#   }
# }
# 性能：DISTINCT后约3-6万条，构建树约300-800ms
#
# 【懒加载模式】适合：大数据量，按需加载
#
# 示例3：获取第一层（所有城市）
# POST /api/tree/lazy
# {
#   "db_key": "village",
#   "table_name": "广东省自然村",
#   "level_columns": [0, 1, 2, 3, 4],
#   "parent_path": null  # 或 []
# }
# 性能：查询第0列的DISTINCT，约10-50ms
# 返回：["广州", "深圳", "珠海", ...]（约21个城市）
#
# 示例4：获取"广州市"下的子节点（所有区县）
# POST /sql/tree/lazy
# {
#   "db_key": "village",
#   "table_name": "广东省自然村",
#   "level_columns": [0, 1, 2, 3, 4],
#   "parent_path": ["广州市"]
# }
# 性能：WHERE 市级='广州'，查询第1列的DISTINCT，约20-80ms
# 返回：["天河区", "越秀区", ...]（约11个区）
#
# 示例5：获取"广州-天河区"下的子节点（所有街道）
# POST /api/tree/lazy
# {
#   "db_key": "village",
#   "table_name": "广东省自然村",
#   "level_columns": [0, 1, 2, 3, 4],
#   "parent_path": ["广州", "天河区"]
# }
# 性能：WHERE 市级='广州' AND 区县级='天河区'，约20-80ms
# 返回：["石牌街道", "五山街道", ...]（约21个街道）
#
# 【组合使用】推荐方案
#
# 方案A：初始懒加载，点击城市后切换到完整树
# 1. 初始：POST /tree/lazy (parent_path=null) - 获取所有城市
# 2. 用户点击"广州"后：POST /tree/full (filters={0:["广州"]}) - 获取广州完整树
# 优点：初始加载快，展开后体验好（不需要多次请求）
#
# 方案B：全程懒加载
# 每次点击都调用 /tree/lazy，传入对应的 parent_path
# 优点：每次请求都很快，服务器压力小
# 缺点：需要多次请求，搜索功能较难实现
#
# ========== 性能分析 ==========
#
# 完整树模式（20万数据，无filters）：
# - DISTINCT查询：可能需要3-10秒（取决于数据分布）
# - 树构建：约500ms-2s
# - 总计：3-12秒（不推荐）
#
# 完整树模式（过滤到1个城市，约1万数据）：
# - DISTINCT查询：约100-500ms
# - 树构建：约50-200ms
# - 总计：150-700ms（可接受）
#
# 懒加载模式（每次查询）：
# - 第一层：约10-50ms
# - 第二层：约20-100ms（取决于父节点）
# - 第三层：约20-100ms
# - 第四层：约20-100ms
# - 第五层：约20-100ms
# - 优点：每次都很快，服务器压力小
#
# ========== 推荐方案 ==========
#
# 推荐使用【方案A：初始懒加载 + 点击后完整树】
#
# 理由：
# 1. 初始加载快：只查询第一层（21个城市），10-50ms
# 2. 展开后体验好：用户点击城市后，加载该城市的完整树（150-700ms），后续不需要再请求
# 3. 支持搜索：有了完整树，可以实现搜索功能
# 4. 服务器压力可控：只在用户点击时才加载完整树
