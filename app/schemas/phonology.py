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
