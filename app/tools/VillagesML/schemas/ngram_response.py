"""
N-gram API 响应模型
Response models for N-gram API endpoints
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Any


class NgramMetadata(BaseModel):
    """N-gram 响应元数据"""
    total_count: int = Field(..., description="返回的记录数")
    note: Optional[str] = Field(None, description="数据说明")
    data_version: Optional[str] = Field(None, description="数据版本")
    coverage_rate: Optional[float] = Field(None, description="数据覆盖率（相对于原始数据）")
    optimization_date: Optional[str] = Field(None, description="数据优化日期")
    includes_insignificant: bool = Field(False, description="是否包含不显著数据")


class NgramResponse(BaseModel):
    """N-gram API 标准响应格式"""
    data: List[dict] = Field(..., description="N-gram 数据列表")
    metadata: NgramMetadata = Field(..., description="响应元数据")


class NgramStatistics(BaseModel):
    """N-gram 统计信息"""
    total_ngrams: int = Field(..., description="N-gram 总数")
    by_level: dict = Field(..., description="按级别统计")
    note: Optional[str] = Field(None, description="说明")
    optimization_date: Optional[str] = Field(None, description="优化日期")
    original_count: Optional[int] = Field(None, description="原始记录数")
    retention_rate: Optional[float] = Field(None, description="保留率")
