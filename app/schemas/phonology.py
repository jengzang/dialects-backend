# schemas/phonology.py

from pydantic import BaseModel, Field, field_validator
from typing import List, Union, Optional, Dict


class AnalysisPayload(BaseModel):
    """
    - 用于 /api/phonology 路由的輸入特徵，分析聲韻。
    - mode: p2s-查詢音位查詢的中古來源 s2p-按中古地位查詢音值
    - locations: 輸入地點（可多個）
    - regions: 輸入分區（某一級分區，例如嶺南，可多個）
    - features: 要查詢的特徵（聲母/韻母/聲調）必須完全匹配，用繁體字
    - status_inputs: 要查詢的中古地位，可帶類名（例如莊組），也可不帶（例如來）；
                   並且支持-全匹配（例如宕-等，會自動匹配宕一、宕三）；後端會進行簡繁轉換，可輸入簡體
                   s2p模式需要的輸入，若留空，則韻母查所有攝，聲母查三十六母，聲調查清濁+調
    - group_inputs: 分組特徵，輸入中古的類名（例如攝，則按韻攝整理某個音位）
                  可輸入簡體，支持簡體轉繁體
                   p2s模式需要的輸入，若不填，則韻母按攝分類，聲母按聲分類，聲調按清濁+調分類。
    - pho_values: 要查詢的具體音值，p2s模式下的輸入，若留空，則查所有音值
    - 若為s2p,返回一個帶有地點、特徵（聲韻調）、分類值（中古地位）、值（具體音值）、對應字（所有查到的字）、
            字數、佔比（在所有查得的值中佔比）、多音字 的數組。p2s也是類似
    """
    mode: str
    locations: List[str] = Field(default_factory=list)
    regions: List[str] = Field(default_factory=list)
    features: List[str] = Field(default_factory=list)
    status_inputs: Union[str, List[str], None] = None
    group_inputs: Union[str, List[str], None] = None
    pho_values: Union[str, List[str], None] = None
    region_mode: str = "yindian"


class CharListRequest(BaseModel):
    path_strings: Optional[List[str]] = None
    column: Optional[List[str]] = None
    combine_query: bool = False
    exclude_columns: Optional[List[str]] = Field(
        default=None,
        description="要排除的列名列表，如 ['多地位標記', '多等']"
    )


class PhonologyMatrixRequest(BaseModel):
    """
    聲母-韻母-聲調矩陣請求模型
    """
    locations: Optional[List[str]] = Field(
        default=None,
        description="地點簡稱列表，不傳則獲取所有地點",
        example=["東莞莞城", "雲浮富林"]
    )


class ZhongGuAnalysis(BaseModel):
    # --- 第一部分：用於查詢漢字 (傳給 process_chars_status/缓存层) ---
    path_strings: Optional[List[str]] = Field(
        ...,
        description="語音條件列表，例如 ['知組', '蟹攝'] 或 ['[知]{組}']",
        example=["[知]{組}", "[莊]{組}"]
    )
    column: Optional[List[str]] = Field(
        default=None,
        description="需要進行排列組合的額外欄位，例如 ['等']",
        example=[]
    )
    combine_query: bool = Field(
        default=False,
        description="是否開啟 path_strings 與 column 的交叉組合查詢"
    )
    exclude_columns: Optional[List[str]] = Field(
        default=None,
        description="要排除的列名列表，如 ['多地位標記', '多等']"
    )

    # --- 第二部分：用於方言分析 (傳給 _run_dialect_analysis_sync) ---
    locations: List[str] = Field(
        ...,
        description="目標地點列表，例如 ['北京', '上海']",
        example=["北京", "广州"]
    )
    regions: List[str] = Field(
        default=[],
        description="目標區域列表（用於輔助查找地點），可留空",
        example=[]
    )
    features: List[str] = Field(
        default=["韻母"],
        description="需要分析的語音特徵",
        example=["聲母", "韻母"]
    )
    # 可選：如果你想控制 region_mode
    region_mode: str = Field(default="yindian", description="地區匹配模式")


class YinWeiAnalysis(BaseModel):
    locations: List[str] = Field(default_factory=list)
    regions: List[str] = Field(default_factory=list)
    features: List[str] = Field(default_factory=list)
    group_inputs: Union[str, List[str], None] = None
    pho_values: Union[str, List[str], None] = None
    region_mode: str = "yindian"
    exclude_columns: Optional[List[str]] = Field(
        default=None,
        description="要排除的列名列表，如 ['多地位標記', '多等']"
    )


    @field_validator('features')
    @classmethod
    def validate_features(cls, v):
        valid_features = {"\u8072\u6bcd", "\u97fb\u6bcd", "\u8072\u8abf"}
        invalid = set(v) - valid_features
        if invalid:
            raise ValueError(f"invalid features: {invalid}; allowed: {valid_features}")
        if not v:
            raise ValueError("features cannot be empty")
        return v


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
        ...,
        description="目标地点列表",
        example=["广州", "香港"]
    )
    regions: List[str] = Field(
        default=[],
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


class PhonologyClassificationMatrixRequest(BaseModel):
    """
    音韻特徵分類矩陣請求模型

    根據用戶指定的分類維度，創建音韻特徵的分類矩陣。
    結合 dialects.db（現代方言讀音）和 characters.db（中古音系分類）。
    """
    locations: List[str] = Field(
        ...,
        description="地點簡稱列表",
        example=["東莞莞城", "雲浮富林"]
    )
    feature: str = Field(
        ...,
        description="音韻特徵：聲母、韻母、聲調",
        example="聲母"
    )
    horizontal_column: str = Field(
        ...,
        description="橫向分類欄位（來自 characters.db）",
        example="母"
    )
    vertical_column: str = Field(
        ...,
        description="縱向分類欄位（來自 characters.db）",
        example="攝"
    )
    cell_row_column: str = Field(
        ...,
        description="單元格內分行欄位（來自 characters.db）",
        example="部位"
    )


class FeatureStatsRequest(BaseModel):
    """
    特徵統計請求模型

    用於 /api/feature_stats 接口，提供音韻特徵的詳細統計分析。
    支持漢字篩選、特徵篩選，並返回索引優化格式的數據。
    """
    locations: List[str] = Field(
        ...,
        description="地點簡稱列表（必需）",
        example=["廣州", "東莞"],
        min_length=1
    )
    chars: Optional[List[str]] = Field(
        default=None,
        description="要查詢的漢字列表（可選，為空則查該地點所有漢字）",
        example=["東", "西", "南", "北"]
    )
    features: List[str] = Field(
        default=["聲母", "韻母", "聲調"],
        description="要統計的特徵列表",
        example=["聲母", "韻母"]
    )
    filters: Optional[Dict[str, List[str]]] = Field(
        default=None,
        description="篩選條件（可選），用於篩選特定的特徵值",
        example={"聲母": ["p", "b"], "韻母": ["a", "ɐ"]}
    )

    @field_validator('features')
    @classmethod
    def validate_features(cls, v):
        """驗證 features 必須是有效的特徵類型"""
        valid_features = {"聲母", "韻母", "聲調"}
        invalid = set(v) - valid_features
        if invalid:
            raise ValueError(f"無效的特徵類型: {invalid}，必須是 {valid_features}")
        if not v:
            raise ValueError("features 不能為空")
        return v

    @field_validator('filters')
    @classmethod
    def validate_filters(cls, v):
        """驗證 filters 的鍵必須是有效的特徵類型"""
        if v is None:
            return v
        valid_features = {"聲母", "韻母", "聲調"}
        invalid = set(v.keys()) - valid_features
        if invalid:
            raise ValueError(f"filters 中的無效鍵: {invalid}，必須是 {valid_features}")
        return v
