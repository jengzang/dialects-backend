# schemas/common/pagination.py
"""
通用分页相关 schemas
"""

from typing import Generic, TypeVar, List
from pydantic import BaseModel, Field

T = TypeVar('T')


class PaginationParams(BaseModel):
    """分页查询参数"""
    page: int = Field(1, ge=1, description="页码，从1开始")
    page_size: int = Field(20, ge=1, le=100, description="每页数量，最大100")


class OffsetPaginationParams(BaseModel):
    """偏移量分页参数"""
    skip: int = Field(0, ge=0, description="跳过的记录数")
    limit: int = Field(20, ge=1, le=100, description="返回的记录数")


class PaginatedResponse(BaseModel, Generic[T]):
    """通用分页响应"""
    total: int = Field(..., description="总记录数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")
    total_pages: int = Field(..., description="总页数")
    data: List[T] = Field(..., description="数据列表")


class OffsetPaginatedResponse(BaseModel, Generic[T]):
    """偏移量分页响应"""
    total: int = Field(..., description="总记录数")
    skip: int = Field(..., description="跳过的记录数")
    limit: int = Field(..., description="返回的记录数")
    data: List[T] = Field(..., description="数据列表")
