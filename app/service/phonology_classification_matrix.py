"""
音韻特徵分類矩陣服務

根據用戶指定的分類維度，創建音韻特徵的分類矩陣。
結合 dialects.db（現代方言讀音）和 characters.db（中古音系分類）。
"""

from typing import List, Dict, Any
from collections import defaultdict
from fastapi import HTTPException

from app.sql.db_pool import get_db_pool
from common.config import CHARACTERS_DB_PATH
from common.constants import HIERARCHY_COLUMNS
from app.service.phonology2status import custom_phonology_sort


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

    # Step 2: 查詢 dialects.db
    pool = get_db_pool(dialect_db_path)
    dialect_data = []

    with pool.get_connection() as conn:
        placeholders = ','.join(f"'{loc}'" for loc in locations)
        query = f"""
            SELECT 簡稱, 漢字, {feature}, 音節, 多音字
            FROM dialects
            WHERE 簡稱 IN ({placeholders})
            AND {feature} IS NOT NULL
        """
        cursor = conn.cursor()
        cursor.execute(query)
        dialect_rows = cursor.fetchall()

        for row in dialect_rows:
            dialect_data.append({
                '簡稱': row[0],
                '漢字': row[1],
                feature: row[2],
                '音節': row[3],
                '多音字': row[4]
            })

    if not dialect_data:
        raise HTTPException(
            status_code=404,
            detail="No data found for the specified locations"
        )

    # Step 3: 獲取唯一漢字列表
    unique_chars = list(set(row['漢字'] for row in dialect_data))

    # Step 4: 查詢 characters.db
    pool = get_db_pool(character_db_path)
    char_classification_map = {}

    with pool.get_connection() as conn:
        placeholders = ','.join(['?'] * len(unique_chars))
        query = f"""
            SELECT 漢字, {horizontal_column}, {vertical_column}, {cell_row_column}
            FROM characters
            WHERE 漢字 IN ({placeholders})
        """
        cursor = conn.cursor()
        cursor.execute(query, unique_chars)
        char_rows = cursor.fetchall()

        for row in char_rows:
            char = row[0]
            h_val = row[1]
            v_val = row[2]
            c_val = row[3]

            # 一個漢字可能有多個分類（多地位字）
            if char not in char_classification_map:
                char_classification_map[char] = []

            char_classification_map[char].append({
                horizontal_column: h_val,
                vertical_column: v_val,
                cell_row_column: c_val
            })

    # Step 5: 構建矩陣
    # 四層嵌套：horizontal → vertical → cell_row → feature_value → [chars]
    matrix = defaultdict(
        lambda: defaultdict(
            lambda: defaultdict(
                lambda: defaultdict(list)
            )
        )
    )

    # 遍歷 dialect_data，填充矩陣
    for row in dialect_data:
        char = row['漢字']
        feature_value = row[feature]

        # 獲取該漢字的分類信息
        classifications = char_classification_map.get(char, [])

        # 對於多地位字，每個地位都要計入
        for classification in classifications:
            h_val = classification.get(horizontal_column)
            v_val = classification.get(vertical_column)
            c_val = classification.get(cell_row_column)

            # 跳過缺失值
            if not all([h_val, v_val, c_val, feature_value]):
                continue

            # 添加到矩陣
            matrix[h_val][v_val][c_val][feature_value].append(char)

    # Step 6: 去重和排序
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

    # Step 7: 收集所有唯一值（中古音系分類用普通排序）
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

    # Step 8: 轉換為普通字典並返回
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
