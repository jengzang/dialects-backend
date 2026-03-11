# schemas/common/response.py
"""
通用响应格式 schemas
"""

from typing import Optional, Any, Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar('T')


class SuccessResponse(BaseModel):
    """成功响应"""
    success: bool = True
    message: Optional[str] = None


class ErrorResponse(BaseModel):
    """错误响应"""
    success: bool = False
    error: str = Field(..., description="错误信息")
    detail: Optional[str] = Field(None, description="详细错误信息")


class DataResponse(BaseModel, Generic[T]):
    """带数据的响应"""
    success: bool = True
    data: T
    message: Optional[str] = None


class MessageResponse(BaseModel):
    """消息响应"""
    message: str = Field(..., description="响应消息")
    success: bool = True
