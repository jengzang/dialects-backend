"""
[PKG] Pydantic 模型：字音比较 API 的请求和响应模型
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator


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


class CompareZhongGuAnalysis(BaseModel):
    """
    比较两组中古音条件在方言中的读音差异
    """
    # --- 第一组中古音条件 ---
    path_strings1: List[str] = Field(
        ...,
        description="第一组语音条件列表",
        example=["[知]{組}"]
    )
    column1: Optional[List[str]] = Field(
        default=None,
        description="第一组的额外排列组合字段",
        example=["等"]
    )
    combine_query1: bool = Field(
        default=False,
        description="第一组是否开启交叉组合查询"
    )
    exclude_columns1: Optional[List[str]] = Field(
        default=None,
        description="第一组要排除的列名列表",
        example=["多地位標記", "多等"]
    )

    # --- 第二组中古音条件 ---
    path_strings2: List[str] = Field(
        ...,
        description="第二组语音条件列表",
        example=["[莊]{組}"]
    )
    column2: Optional[List[str]] = Field(
        default=None,
        description="第二组的额外排列组合字段",
        example=["等"]
    )
    combine_query2: bool = Field(
        default=False,
        description="第二组是否开启交叉组合查询"
    )
    exclude_columns2: Optional[List[str]] = Field(
        default=None,
        description="第二组要排除的列名列表",
        example=["多地位標記", "多等"]
    )

    # --- 方言分析参数 ---
    locations: List[str] = Field(
        default_factory=list,
        description="目标地点列表",
        example=["广州", "香港"]
    )
    regions: List[str] = Field(
        default_factory=list,
        description="目标区域列表",
        example=[]
    )
    features: List[str] = Field(
        default=["韻母"],
        description="需要比较的语音特征",
        example=["聲母", "韻母"]
    )
    region_mode: str = Field(
        default="yindian",
        description="地区匹配模式"
    )
    table_name: str = Field(
        default="characters",
        description="字符數據庫表名（兩組使用相同表）"
    )

    @model_validator(mode="after")
    def check_locations_or_regions(self):
        if not self.locations and not self.regions:
            raise ValueError("locations 和 regions 不能同時為空，至少提供其一")
        return self

    @field_validator('table_name')
    @classmethod
    def validate_table_name(cls, v):
        from app.common.constants import VALID_CHARACTER_TABLES
        if v not in VALID_CHARACTER_TABLES:
            raise ValueError(f"Invalid table_name: {v}. Must be one of {VALID_CHARACTER_TABLES}")
        return v
