"""
[PKG] Pydantic 模型：字音比较 API 的请求和响应模型
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class CompareCharsRequest(BaseModel):
    """字音比较请求模型"""
    chars: List[str] = Field(..., description="要比较的汉字列表", min_length=2)
    features: List[str] = Field(..., description="要比较的特征列表，可选：聲母/韻母/聲調", min_length=1)
    locations: Optional[List[str]] = Field(None, description="要查询的地点列表")
    regions: Optional[List[str]] = Field(None, description="要查询的分区列表")
    region_mode: str = Field("yindian", description="分区模式，可选 'yindian' 或 'map'")


class FeatureComparison(BaseModel):
    """单个特征的比较结果"""
    status: str = Field(..., description="比较状态：same/diff/partial/unknown")
    value: Optional[str] = Field(None, description="当 status=same 时的共同值")
    values: Optional[Dict[str, List[str]]] = Field(None, description="当 status=diff/partial/unknown 时各字的值")


class PairComparison(BaseModel):
    """一对字的比较结果"""
    pair: List[str] = Field(..., description="比较的字对")
    features: Dict[str, FeatureComparison] = Field(..., description="各特征的比较结果")


class LocationComparison(BaseModel):
    """单个地点的比较结果"""
    location: str = Field(..., description="地点名称")
    comparisons: List[PairComparison] = Field(..., description="所有字对的比较结果")


class CompareCharsResponse(BaseModel):
    """字音比较响应模型"""
    results: List[LocationComparison] = Field(..., description="各地点的比较结果")
