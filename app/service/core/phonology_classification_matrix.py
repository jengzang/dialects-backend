"""
音韻特徵分類矩陣服務

根據用戶指定的分類維度，創建音韻特徵的分類矩陣。
結合 dialects.db（現代方言讀音）和 characters.db（中古音系分類）。
"""

from typing import List, Dict, Any
from collections import defaultdict
from fastapi import HTTPException

from app.sql.db_pool import get_db_pool
from app.common.path import CHARACTERS_DB_PATH
from app.common.constants import HIERARCHY_COLUMNS
from app.service.core.phonology2status import custom_phonology_sort


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
