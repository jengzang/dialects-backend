from typing import Optional, Dict, List, Any

from pydantic import BaseModel


class QueryParams(BaseModel):
    db_key: str
    table_name: str
    page: int = 1
    page_size: int = 20
    sort_by: Optional[str] = None
    sort_desc: bool = False
    filters: Dict[str, List[Any]] = {} # 格式: {"city": ["Beijing", "Shanghai"], "status": [1]}
    search_text: Optional[str] = None  # 全局搜索文本
    search_columns: List[str] = []     # 参与搜索的列名列表（前端传过来）

class MutationParams(BaseModel):
    db_key: str
    table_name: str
    action: str # "create", "update", "delete"
    pk_column: str = "rowid" # 主键列名，默认id
    pk_value: Any = None
    data: Dict[str, Any] = {}


class DistinctQueryRequest(BaseModel):
    db_key: str
    table_name: str
    target_column: str              # 我們要獲取哪一列的唯一值
    current_filters: Dict[str, List[Any]] = {} # 其他列的篩選狀態，例如 {"city": ["Beijing"], "status": [null]}
    search_text: Optional[str] = "" # 全局搜索詞
    search_columns: List[str] = []  # 哪些列參與全局搜索


class BatchMutationParams(BaseModel):
    """批量操作参数"""
    db_key: str
    table_name: str
    action: str  # "batch_create", "batch_update", "batch_delete"
    pk_column: str = "rowid"  # 主键列名，默认id

    # 批量创建：多条记录数据
    create_data: List[Dict[str, Any]] = []

    # 批量更新：多条记录数据（必须包含主键）
    update_data: List[Dict[str, Any]] = []

    # 批量删除：主键值列表
    delete_ids: List[Any] = []


# ========== tree数据模型 ==========
class FullTreeParams(BaseModel):
    """完整树模式参数"""
    db_key: str
    table_name: str
    level_columns: List[int]  # 列号从0开始，例如 [0, 1, 2, 3, 4]
    data_columns: List[int] = []  # 新增参数，默认为空列表，兼容旧逻辑
    filters: Optional[Dict[int, List[str]]] = None  # 键是列号，值是过滤值列表


class LazyTreeParams(BaseModel):
    """懒加载模式参数"""
    db_key: str
    table_name: str
    level_columns: List[int]  # 列号从0开始
    parent_path: Optional[List[str]] = None  # 父节点路径，None或[]表示第一层
    filters: Optional[Dict[int, List[str]]] = None  # 键是列号


class BatchReplacePreviewParams(BaseModel):
    """批量替换预览参数"""
    db_key: str
    table_name: str
    columns: List[str]  # 需要查找/替换的列名数组
    find_text: str  # 查找文本（空字符串表示查找空值）
    match_mode: str  # 匹配模式："exact"(完全匹配) 或 "contains"(包含匹配)
    is_empty_search: bool  # 是否为空值查找
    filters: Dict[str, List[Any]] = {}  # 当前应用的筛选条件（可选）
    search_text: Optional[str] = ""  # 当前搜索关键词（可选）


class BatchReplaceExecuteParams(BaseModel):
    """批量替换执行参数"""
    db_key: str
    table_name: str
    pk_column: str = "rowid"  # 主键列名
    columns: List[str]  # 需要查找/替换的列名数组
    find_text: str  # 查找文本
    replace_text: str  # 替换后的文本
    match_mode: str  # 匹配模式："exact" 或 "contains"
    is_empty_search: bool  # 是否为空值查找
    filters: Dict[str, List[Any]] = {}  # 筛选条件
    search_text: Optional[str] = ""  # 搜索关键词