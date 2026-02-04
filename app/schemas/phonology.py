# schemas/phonology.py

from pydantic import BaseModel, Field
from typing import List, Union, Optional


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
