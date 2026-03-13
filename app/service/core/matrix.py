"""
音韻特徵分類矩陣服務

根據用戶指定的分類維度，創建音韻特徵的分類矩陣。
結合 dialects.db（現代方言讀音）和 characters.db（中古音系分類）。
"""

from typing import List, Dict, Any
from collections import defaultdict
from fastapi import HTTPException

from app.sql.db_pool import get_db_pool
from app.common.path import CHARACTERS_DB_PATH, DIALECTS_DB_USER
from app.common.constants import HIERARCHY_COLUMNS, custom_order

MERGE_MAP = {}
# IPA 符號合併映射表
MERGE_MAP.update({k: "kʷ" for k in ["kw", "kᵘ", "kᵛ", "kʋ", "kʷ", "kv"]})
MERGE_MAP.update({k: "kʰw" for k in ["kʷʰ", "kʰʷ", "kʰᵘ", "kʰᵛ", "kʰʋ", "kʋʰ", "kʰw", "kvʰ"]})
MERGE_MAP.update({k: "pʰʋ" for k in ["pʰw", "pʰᵘ", "pʰʋ"]})
MERGE_MAP.update({k: "tʰw" for k in ["tʰᵘ", "tʰw", "tʰʋ"]})
MERGE_MAP.update({k: "ʔ" for k in ["(ʔ)", "∅", "ʔ", "ˀ"]})
MERGE_MAP.update({k: "ʋ" for k in ["v", "ʋ", "vʋ", "w"]})
MERGE_MAP.update({k: "h" for k in ["h", "ɦ", "ɦʰ", "xʱ", "hɦ", "hʱ", "ʰ"]})
MERGE_MAP.update({k: "hʷ" for k in ["hʷ", "hw", "hʋ", "ɦʋ"]})
MERGE_MAP.update({k: "x" for k in ["x", "xʱ", "xɣ", "ɣ", "χ"]})
MERGE_MAP.update({k: "xʷ" for k in ["xv", "xʋ", "xʷ", "xᵊ", "xᶷ"]})
MERGE_MAP.update({k: "d" for k in ["d", "d̥", "ɗ", "ɗw"]})
MERGE_MAP.update({k: "dz" for k in ["dz", "d̥z̥"]})
MERGE_MAP.update({k: "dʑ" for k in ["dʑ", "d̥ʑ̥"]})
MERGE_MAP.update({k: "fw" for k in ["fʋ", "fw", "fv", "fʰ", "fʱ", "f", "̊f"]})
MERGE_MAP.update({k: "l" for k in ["l", "l̥", "l̩"]})
MERGE_MAP.update({k: "m" for k in ["m", "m̥", "m̩", "m͡b"]})
MERGE_MAP.update({k: "mʷ" for k in ["mʷ", "mw", "mʋ"]})
MERGE_MAP.update({k: "mʰ" for k in ["mʰ", "mɦ", "mʱ"]})
MERGE_MAP.update({k: "sʷ" for k in ["sw", "sʋ", "sʷ"]})
MERGE_MAP.update({k: "tʰ" for k in ["tʰʰ", "tʱ", "tʰ"]})
MERGE_MAP.update({k: "ŋʷ" for k in ["ŋʷ", "ŋw", "ŋʋ"]})
MERGE_MAP.update({k: "ŋ" for k in ["ŋ", "ŋ̊", "ŋɡ", "ŋ͡ɡ", "ng", "nɡ"]})
MERGE_MAP.update({k: "ɡ" for k in ["ɡ", "g", "ɡ̊", "ᵑɡ"]})
MERGE_MAP.update({k: "b" for k in ["b̥", "ɓw", "ɓ", "ᵐb", "b", "bv"]})

def custom_phonology_sort(items):
    """
    使用 custom_order 對音韻符號進行排序
    支持多字符 IPA 符號（如 pʰ, tʰ）

    Args:
        items: 要排序的音韻符號列表

    Returns:
        排序後的列表
    """
    def sort_key(item):
        # 先應用 MERGE_MAP 標準化
        normalized = MERGE_MAP.get(item, item)

        # 按照 custom_order 中的位置排序
        # 對於多字符符號，逐字符匹配
        return [
            custom_order.index(normalized[i:i + 2]) if normalized[i:i + 2] in custom_order else
            custom_order.index(normalized[i]) if normalized[i] in custom_order else float('inf')
            for i in range(len(normalized))
        ]

    return sorted(items, key=sort_key)



def build_phonology_classification_matrix(
    locations: List[str],
    feature: str,
    horizontal_column: str,
    vertical_column: str,
    cell_row_column: str,
    dialect_db_path: str,
    character_db_path: str = CHARACTERS_DB_PATH
) -> Dict[str, Any]:
    """
    構建音韻特徵分類矩陣

    Args:
        locations: 地點簡稱列表
        feature: 音韻特徵（聲母、韻母、聲調）
        horizontal_column: 橫向分類欄位
        vertical_column: 縱向分類欄位
        cell_row_column: 單元格內分行欄位
        dialect_db_path: 方言數據庫路徑
        character_db_path: 漢字數據庫路徑

    Returns:
        包含矩陣數據的字典
    """
    # Step 1: 參數驗證
    valid_features = ["聲母", "韻母", "聲調"]
    if feature not in valid_features:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid feature. Must be one of: {valid_features}"
        )

    valid_columns = HIERARCHY_COLUMNS
    for col in [horizontal_column, vertical_column, cell_row_column]:
        if col not in valid_columns:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid column '{col}'. Must be one of: {valid_columns}"
            )

    if not locations:
        raise HTTPException(status_code=400, detail="Locations cannot be empty")

    # Step 2: 使用 SQL JOIN 合併兩個數據庫的查詢
    pool = get_db_pool(dialect_db_path)

    with pool.get_connection() as conn:
        cursor = conn.cursor()

        # ATTACH characters.db 以便進行 JOIN
        cursor.execute(f"ATTACH DATABASE '{character_db_path}' AS chars_db")

        placeholders = ','.join(f"'{loc}'" for loc in locations)
        query = f"""
            SELECT
                d.漢字,
                d.{feature} as feature_value,
                c.{horizontal_column} as h_val,
                c.{vertical_column} as v_val,
                c.{cell_row_column} as c_val
            FROM dialects d
            INNER JOIN chars_db.characters c ON d.漢字 = c.漢字
            WHERE d.簡稱 IN ({placeholders})
              AND d.{feature} IS NOT NULL
              AND c.{horizontal_column} IS NOT NULL
              AND c.{vertical_column} IS NOT NULL
              AND c.{cell_row_column} IS NOT NULL
        """
        cursor.execute(query)
        joined_rows = cursor.fetchall()

        # DETACH characters.db
        cursor.execute("DETACH DATABASE chars_db")

    if not joined_rows:
        raise HTTPException(
            status_code=404,
            detail="No data found for the specified locations"
        )

    # Step 3: 構建矩陣
    # 四層嵌套：horizontal → vertical → cell_row → feature_value → [chars]
    matrix = defaultdict(
        lambda: defaultdict(
            lambda: defaultdict(
                lambda: defaultdict(list)
            )
        )
    )

    # 遍歷 JOIN 結果，填充矩陣
    for row in joined_rows:
        char = row[0]
        feature_value = row[1]
        h_val = row[2]
        v_val = row[3]
        c_val = row[4]

        # 添加到矩陣
        matrix[h_val][v_val][c_val][feature_value].append(char)

    # Step 4: 去重和排序
    # 收集所有 feature values 用於排序
    all_feature_values = set()
    for h_val in matrix:
        for v_val in matrix[h_val]:
            for c_val in matrix[h_val][v_val]:
                all_feature_values.update(matrix[h_val][v_val][c_val].keys())

    # 使用自定義排序對 feature values 排序
    sorted_feature_values = custom_phonology_sort(list(all_feature_values))
    feature_value_order = {val: idx for idx, val in enumerate(sorted_feature_values)}

    # 對每個單元格的漢字去重並排序
    for h_val in matrix:
        for v_val in matrix[h_val]:
            for c_val in matrix[h_val][v_val]:
                for f_val in matrix[h_val][v_val][c_val]:
                    chars = matrix[h_val][v_val][c_val][f_val]
                    matrix[h_val][v_val][c_val][f_val] = sorted(list(set(chars)))

    # Step 5: 收集所有唯一值（中古音系分類用普通排序）
    horizontal_values = sorted(matrix.keys())

    vertical_values_set = set()
    for h_val in matrix:
        vertical_values_set.update(matrix[h_val].keys())
    vertical_values = sorted(vertical_values_set)

    cell_row_values_set = set()
    for h_val in matrix:
        for v_val in matrix[h_val]:
            cell_row_values_set.update(matrix[h_val][v_val].keys())
    cell_row_values = sorted(cell_row_values_set)

    # Step 6: 轉換為普通字典並返回
    def convert_to_dict(d):
        """將 defaultdict 轉換為普通 dict（便於 JSON 序列化）"""
        if isinstance(d, defaultdict):
            d = {k: convert_to_dict(v) for k, v in d.items()}
        return d

    matrix_dict = convert_to_dict(matrix)

    return {
        "locations": locations,
        "feature": feature,
        "horizontal_column": horizontal_column,
        "vertical_column": vertical_column,
        "cell_row_column": cell_row_column,
        "horizontal_values": horizontal_values,
        "vertical_values": vertical_values,
        "cell_row_values": cell_row_values,
        "matrix": matrix_dict
    }

def get_all_phonology_matrices(locations=None, db_path=DIALECTS_DB_USER, table="dialects"):
    """
    获取指定地点的声母-韵母-汉字交叉表数据

    Args:
        locations: 地点列表，如果为 None 则获取所有地点
        db_path: 数据库路径
        table: 表名

    Returns:
        {
            "locations": List[str],
            "data": {
                "地点1": {
                    "initials": List[str],
                    "finals": List[str],
                    "tones": List[str],
                    "matrix": Dict[str, Dict[str, Dict[str, List[str]]]]
                },
                ...
            }
        }
    """
    # 参数验证：必须提供地点列表
    if not locations or len(locations) == 0:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail="locations parameter is required and cannot be empty"
        )

    # 参数验证：限制地点数量
    if len(locations) > 50:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail=f"Too many locations. Maximum 50 locations allowed, got {len(locations)}"
        )

    pool = get_db_pool(db_path)
    with pool.get_connection() as conn:
        cursor = conn.cursor()

        # 使用 SQL GROUP_CONCAT 聚合汉字
        placeholders = ','.join(f"'{loc}'" for loc in locations)
        query = f"""
            SELECT 簡稱, 聲母, 韻母, 聲調, GROUP_CONCAT(漢字, '') as 漢字列表
            FROM {table}
            WHERE 簡稱 IN ({placeholders})
              AND 簡稱 IS NOT NULL
              AND 聲母 IS NOT NULL
              AND 韻母 IS NOT NULL
              AND 聲調 IS NOT NULL
              AND 漢字 IS NOT NULL
            GROUP BY 簡稱, 聲母, 韻母, 聲調
            ORDER BY 簡稱, 聲母, 韻母, 聲調
        """

        cursor.execute(query)
        rows = cursor.fetchall()

    # 按地点分组的数据
    locations_data = defaultdict(lambda: {
        "matrix": defaultdict(lambda: defaultdict(dict)),
        "initials": set(),
        "finals": set(),
        "tones": set()
    })

    # 处理查询结果
    for row in rows:
        location = row[0]  # 地点
        initial = row[1]   # 声母
        final = row[2]     # 韵母
        tone = row[3]      # 声调
        chars_str = row[4]  # 汉字列表（已聚合）

        # 转换为字符列表
        chars_list = list(chars_str) if chars_str else []

        # 添加到该地点的矩阵
        loc_data = locations_data[location]
        loc_data["matrix"][initial][final][tone] = chars_list

        # 收集该地点的唯一值
        loc_data["initials"].add(initial)
        loc_data["finals"].add(final)
        loc_data["tones"].add(tone)

    # 转换为最终格式
    result = {
        "locations": sorted(list(locations_data.keys())),
        "data": {}
    }

    for location, loc_data in locations_data.items():
        result["data"][location] = {
            "initials": custom_phonology_sort(list(loc_data["initials"])),
            "finals": custom_phonology_sort(list(loc_data["finals"])),
            "tones": custom_phonology_sort(list(loc_data["tones"])),
            "matrix": {
                initial: {
                    final: dict(tones_dict)
                    for final, tones_dict in finals_dict.items()
                }
                for initial, finals_dict in loc_data["matrix"].items()
            }
        }

    return result
