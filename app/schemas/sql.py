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