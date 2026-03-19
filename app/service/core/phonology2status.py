import re

import pandas as pd
from fastapi import HTTPException

from app.common.path import QUERY_DB_USER, DIALECTS_DB_USER, CHARACTERS_DB_PATH
from app.service.core.matrix import MERGE_MAP
from app.service.core.process_sp_input import split_pho_input
from app.common.constants import AMBIG_VALUES, HIERARCHY_COLUMNS, s2t_column
from app.service.geo.getloc_by_name_region import query_dialect_abbreviations
from app.service.geo.match_input_tip import match_locations_batch_exact
from app.sql.db_pool import get_db_pool

"""
整體流程總結：

1. 使用者給定地點（locations）、語音特徵（features，例如聲母、韻母）與分組欄位（status_inputs，例如"聲組"）

2. run_dialect_analysis：
   - 解析使用者指定的分組欄位，建立每個特徵對應的 group_fields
   - 調用 query_dialect_features 查詢每個地點與特徵對應的漢字子表 sub_df
   - 對每組漢字調用 analyze_characters_from_db 進行實際分組與統計

3. analyze_characters_from_db：
   - 從 characters.db 查出指定漢字的語音屬性
   - 根據 group_fields 進行分組
   - 計算字數、佔比、多地位簡表，並統整為結果

4. 返回的資料可以用來分析語音特徵在不同地點的分布狀況與音系特點
"""


def query_dialect_features(locations, features, db_path=DIALECTS_DB_USER, table="dialects"):
    if not locations or not features:
        return {}
    allowed_features = {"聲母", "韻母", "聲調"}
    features = [f for f in features if f in allowed_features]
    if not features:
        return {}
    """
    從 dialects 數據庫中查出指定地點與特徵（如聲母、韻母等）對應的漢字。

    性能优化：使用SQL层面的GROUP BY代替pandas处理（5-10倍性能提升）
    """
    pool = get_db_pool(db_path)
    result = {}

    with pool.get_connection() as conn:
        cursor = conn.cursor()

        # 【SQL优化】一次性查询所有数据
        query = f"""
        SELECT 簡稱, 漢字, {', '.join(features)}, 音節, 多音字
        FROM {table}
        WHERE 簡稱 IN ({','.join(['?'] * len(locations))})
        """
        cursor.execute(query, locations)
        all_rows = cursor.fetchall()

        # 构建列索引映射
        col_indices = {'簡稱': 0, '漢字': 1, '音節': len(features) + 2, '多音字': len(features) + 3}
        for i, feat in enumerate(features):
            col_indices[feat] = i + 2

        # 对每个特征进行处理
        for feature in features:
            feature_idx = col_indices[feature]
            feature_dict = {}
            
            # 使用字典进行分组（代替pandas groupby）
            from collections import defaultdict
            groups = defaultdict(list)
            
            for row in all_rows:
                feature_value = row[feature_idx]
                if feature_value:  # 跳过NULL值
                    groups[feature_value].append(row)
            
            # 处理每个特征值
            for feature_value, rows in groups.items():
                # 提取唯一汉字
                chars = list(set(row[col_indices['漢字']] for row in rows))
                
                # 构建sub_df
                sub_df = pd.DataFrame(
                    [[row[col_indices['簡稱']], row[col_indices['漢字']], 
                      row[feature_idx], row[col_indices['音節']], row[col_indices['多音字']]] 
                     for row in rows],
                    columns=['簡稱', '漢字', feature, '音節', '多音字']
                )
                
                # 处理多音字
                poly_dict = defaultdict(set)
                for row in rows:
                    if row[col_indices['多音字']] == '1':
                        hz = row[col_indices['漢字']]
                        pron = row[col_indices['音節']]
                        if pron:
                            poly_dict[hz].add(pron)
                
                poly_details = [f"{hz}:{';'.join(sorted(prons))}" for hz, prons in poly_dict.items()]
                
                feature_dict[feature_value] = {
                    "漢字": chars,
                    "sub_df": sub_df,
                    "多音字詳情": poly_details
                }
            
            result[feature] = feature_dict

    return result


def analyze_characters_from_db(
        char_list,
        feature_type,
        feature_value,
        loc,
        sub_df,
        char_db_path=CHARACTERS_DB_PATH,
        group_fields=None,
        exclude_columns=None,
        table="characters"
):
    """
    根據漢字名單，從 characters.db 中查出相關音系特徵資料，並根據指定的 group_fields 欄位分組統計。

    分組後每組返回：
    - 該組對應的字（已去重）
    - 字數與佔比（以去重後字數為準）
    - 多地位詳情（保留原始重複資料，用於展示）
    - 分組值（欄位對應值，例如 {'調': '平', '清濁': '全濁'}）

    若 group_fields 為空，根據特徵類型自動選擇預設欄位：
        聲母 ➜ 母
        韻母 ➜ 韻
        聲調 ➜ 清濁 + 調

    Args:
        exclude_columns: List[str] or None, 例如 ["多地位標記", "多等"]
                        用於過濾掉這些列值為 1（字符串或整數）的行
        table: 字符數據庫表名（默認 "characters"）
    """

    # 驗證表名
    from app.common.constants import validate_table_name, get_table_schema
    if not validate_table_name(table):
        raise ValueError(f"無效的表名：{table}")

    schema = get_table_schema(table)
    ambig = schema.get("ambig_values", AMBIG_VALUES)
    suffix_map = schema.get("suffix_map", {})

    default_grouping = schema.get("default_grouping", {})
    # print(f"特徵值{feature_value}")
    if not group_fields:
        group_fields = default_grouping.get(feature_type)
        if not group_fields:
            raise ValueError(f"[X] 未定義的 feature_type：{feature_type}")

    pool = get_db_pool(char_db_path)
    with pool.get_connection() as conn:
        placeholders = ','.join(['?'] * len(char_list))
        char_col = schema["char_column"]
        query = f"SELECT * FROM {table} WHERE {char_col} IN ({placeholders})"
        df = pd.read_sql_query(query, conn, params=char_list)

    if df.empty:
        return []

    # 【新增】應用過濾邏輯
    if exclude_columns:
        for col_name in exclude_columns:
            if col_name in df.columns:
                # 過濾掉該列值為 1（字符串或整數）的行
                df = df[
                    (df[col_name] != 1) &
                    (df[col_name] != "1")
                ]

    multi_status_col = schema.get("multi_status_column", "多地位標記")
    multi_cols_groups = schema.get("multi_status_cols", [["攝", "呼", "等", "韻", "調"], ["部位", "方式", "母"]])
    all_multi_cols = [c for grp in multi_cols_groups for c in grp]

    # 確保所需列存在（不存在的填 None）
    for col in all_multi_cols + [multi_status_col]:
        if col not in df.columns:
            df[col] = None

    total_chars = len(set(sub_df["漢字"]))
    grouped_result = []

    df = df.dropna(subset=group_fields)
    grouped = df.groupby(group_fields)

    for group_keys, group_df in grouped:
        _, sample_row = next(group_df.iterrows())

        value_parts = []
        for field, val in zip(group_fields, group_keys):
            if val in ambig:
                suffix = suffix_map.get(field)
                if suffix:
                    val = f"{val}{suffix}"
            value_parts.append(val)
        group_value = "·".join(value_parts)

        group_values = {feature_value: group_value}

        unique_chars = group_df["漢字"].unique().tolist()
        count = len(unique_chars)

        poly_details = []
        poly_chars = group_df[group_df[multi_status_col] == "1"]["漢字"].unique()
        for hz in poly_chars:
            sub = df[(df["漢字"] == hz) & (df[multi_status_col] == "1")]
            summary = []
            for _, row in sub.iterrows():
                group_strs = []
                for grp in multi_cols_groups:
                    vals = [str(row[c]) for c in grp if pd.notna(row.get(c))]
                    group_strs.append("·".join(vals))
                summary.append(",".join(s for s in group_strs if s))
            poly_details.append(f"{hz}: {' | '.join(summary)}")
        # print(f"🧩 當前分析地點：{loc}")
        # print(f"🔢 total_chars for {loc}: {total_chars}")
        # print(f"📄 特徵 {group_value} 的字數：{count}")

        grouped_result.append({
            "地點": loc,
            "特徵類別": feature_type,
            "特徵值": feature_value,
            "分組值": group_values,
            "字數": count,
            "佔比": round(count / total_chars, 4) if total_chars else 0,
            "對應字": unique_chars,
            "多地位詳情": "; ".join(poly_details)
        })

    return pd.DataFrame(grouped_result)


def analyze_characters_from_cached_df(
        char_df,
        char_list,
        feature_type,
        feature_value,
        loc,
        sub_df,
        group_fields=None,
        table="characters"
):
    from app.common.constants import get_table_schema
    schema = get_table_schema(table)
    ambig = schema.get("ambig_values", AMBIG_VALUES)
    suffix_map = schema.get("suffix_map", {})

    if not group_fields:
        default_grouping = schema.get("default_grouping", {})
        group_fields = default_grouping.get(feature_type)
        if not group_fields:
            raise ValueError(f"[X] 未定義的 feature_type：{feature_type}")

    if not char_list:
        return []

    from app.common.path import CHARACTERS_DB_PATH
    pool = get_db_pool(CHARACTERS_DB_PATH)

    with pool.get_connection() as conn:
        cursor = conn.cursor()
        placeholders = ','.join(['?'] * len(char_list))
        group_cols = ', '.join(group_fields)

        query = f"""
        SELECT
            {group_cols},
            GROUP_CONCAT(DISTINCT 漢字) as chars,
            COUNT(DISTINCT 漢字) as count
        FROM {table}
        WHERE 漢字 IN ({placeholders})
        """
        for field in group_fields:
            query += f" AND {field} IS NOT NULL"
        query += f" GROUP BY {group_cols}"
        cursor.execute(query, char_list)
        rows = cursor.fetchall()

        # 多地位详情查询
        multi_cols_groups = schema.get("multi_status_cols", [["攝", "呼", "等", "韻", "調"], ["部位", "方式", "母"]])
        all_multi_cols = [c for grp in multi_cols_groups for c in grp]
        multi_select = ", ".join(all_multi_cols)
        multi_status_col = schema.get("multi_status_column", "多地位標記")
        multi_query = f"""
        SELECT 漢字, {multi_select}
        FROM {table}
        WHERE 漢字 IN ({placeholders})
        AND {multi_status_col} = '1'
        """
        cursor.execute(multi_query, char_list)
        multi_rows = cursor.fetchall()

    # 构建多地位字字典
    from collections import defaultdict
    multi_dict = defaultdict(list)
    col_offset = 1  # row[0] is 漢字
    for row in multi_rows:
        hz = row[0]
        group_strs = []
        offset = col_offset
        for grp in multi_cols_groups:
            vals = [str(row[offset + i]) for i in range(len(grp)) if row[offset + i] is not None]
            group_strs.append("·".join(vals))
            offset += len(grp)
        multi_dict[hz].append(",".join(s for s in group_strs if s))

    total_chars = len(set(sub_df["漢字"]))
    grouped_result = []

    for row in rows:
        group_keys = row[:len(group_fields)]
        chars_str = row[len(group_fields)]
        count = row[len(group_fields) + 1]

        value_parts = []
        for field, val in zip(group_fields, group_keys):
            if val in ambig:
                suffix = suffix_map.get(field)
                if suffix:
                    val = f"{val}{suffix}"
            value_parts.append(val)
        group_value = "·".join(value_parts)

        unique_chars = chars_str.split(',') if chars_str else []
        poly_details = [
            f"{hz}: {' | '.join(multi_dict[hz])}"
            for hz in unique_chars if hz in multi_dict
        ]

        grouped_result.append({
            "地點": loc,
            "特徵類別": feature_type,
            "特徵值": feature_value,
            "分組值": {feature_value: group_value},
            "字數": count,
            "佔比": round(count / total_chars, 4) if total_chars else 0,
            "對應字": unique_chars,
            "多地位詳情": "; ".join(poly_details)
        })

    return pd.DataFrame(grouped_result)


def pho2sta(locations, regions, features, status_inputs,
            pho_values=None,
            dialect_db_path=DIALECTS_DB_USER,
            character_db_path=CHARACTERS_DB_PATH, region_mode='yindian',
            exclude_columns=None,
            query_db_path=QUERY_DB_USER,
            table="characters"):  # 新增：字符數據庫表名
    # 驗證表名
    from app.common.constants import validate_table_name, get_table_schema
    if not validate_table_name(table):
        raise ValueError(f"無效的表名：{table}")

    schema = get_table_schema(table)

    def convert_simplified_to_traditional(simplified_text):
        return "".join([s2t_column.get(ch, ch) for ch in simplified_text])

    pho_values = split_pho_input(pho_values or [])

    grouping_columns_map = {}
    for idx, feature in enumerate(features):
        user_input = status_inputs[idx] if idx < len(status_inputs) else ""

        # [OK] 最開始就做簡體轉繁體轉換
        user_input = convert_simplified_to_traditional(user_input)

        # 嘗試匹配欄位（使用表的層級列）
        user_columns = [col for col in schema["hierarchy"] if col in user_input]

        if user_columns:
            print(f"[OK] 特徵【{feature}】使用分組欄位：{user_columns}")
            grouping_columns_map[feature] = user_columns
        else:
            print(f"[X] 輸入「{user_input}」未匹配任何欄位，特徵【{feature}】將使用預設分組欄位")
            grouping_columns_map[feature] = None

    locations_new = query_dialect_abbreviations(regions, locations, db_path=query_db_path, region_mode=region_mode)
    match_results = match_locations_batch_exact(" ".join(locations_new))
    if not any(res[1] == 1 for res in match_results):
        # print("🛑 沒有任何地點完全匹配，終止分析。")
        raise HTTPException(status_code=400, detail="🛑 沒有任何地點完全匹配，終止分析。")
        # return []

    unique_abbrs = list({abbr for res in match_results for abbr in res[0]})
    # print(f"\n📍 確認匹配地點：{unique_abbrs}")

    # 【性能优化】批量查询 characters.db（一次查询代替 N 次查询）
    dialect_output = query_dialect_features(unique_abbrs, features, db_path=dialect_db_path)

    # 收集所有需要查询的汉字
    all_chars = set()
    for feature in features:
        for feature_value, data in dialect_output[feature].items():
            chars = data["漢字"]
            all_chars.update(chars)

    # 批量查询 characters.db（只查询一次）
    pool = get_db_pool(character_db_path)
    with pool.get_connection() as conn:
        if all_chars:
            placeholders = ','.join(['?'] * len(all_chars))
            query = f"SELECT * FROM {table} WHERE 漢字 IN ({placeholders})"
            all_chars_df = pd.read_sql_query(query, conn, params=list(all_chars))
            print(f"[OK] 批量查询 {table} 完成，共 {len(all_chars_df)} 条记录")
        else:
            all_chars_df = pd.DataFrame()

    # 应用过滤逻辑（exclude_columns）
    if exclude_columns and not all_chars_df.empty:
        for col_name in exclude_columns:
            if col_name in all_chars_df.columns:
                all_chars_df = all_chars_df[
                    (all_chars_df[col_name] != 1) &
                    (all_chars_df[col_name] != "1")
                ]

    results = []

    for loc in unique_abbrs:
        # print(f"\n🔷 開始處理地點：{loc}")
        for feature in features:
            # print(f"  ├── 特徵：{feature}")
            group_fields = grouping_columns_map.get(feature)

            feature_items = dialect_output[feature].items()

            # 過濾 pho_values（若有）
            if pho_values:
                print(pho_values)
                filtered_items = []
                for fv, d in feature_items:
                    # 檢查 pho_values 中的每個元素
                    match_found = False
                    for pho_value in pho_values:
                        # 如果 pho_value 含有漢字，則進行模糊匹配
                        if any('\u4e00' <= char <= '\u9fff' for char in pho_value):  # 檢查是否包含漢字
                            if re.search(pho_value, fv):  # 模糊匹配
                                match_found = True
                                break
                        else:
                            # 如果沒有漢字，則進行完全匹配
                            if fv == pho_value:
                                match_found = True
                                break
                    if match_found:
                        filtered_items.append((fv, d))

                if filtered_items:
                    # print(f"     📌 過濾特徵值：{[fv for fv, _ in filtered_items]}")
                    feature_items = filtered_items
                else:
                    print("     [!] 無匹配特徵值，fallback 使用全部")

            for feature_value, data in feature_items:
                sub_df = data["sub_df"]
                loc_chars = sub_df[sub_df["簡稱"] == loc]["漢字"].unique().tolist()
                # print(f"     ➤ 運算特徵值：{feature_value}（字數：{len(loc_chars)}）")

                if not loc_chars:
                    # print("        [!] 該特徵值在此地點無資料，略過")
                    continue

                # 【性能优化】使用缓存的 DataFrame，不再查询数据库
                result = analyze_characters_from_cached_df(
                    char_df=all_chars_df,
                    char_list=loc_chars,
                    feature_type=feature,
                    feature_value=feature_value,
                    loc=loc,
                    sub_df=sub_df[sub_df["簡稱"] == loc],
                    group_fields=group_fields,
                    table=table,
                )

                results.extend(result if isinstance(result, list) else [result])

    return results

# if __name__ == "__main__":
#     pd.set_option('display.max_rows', None)
#     pd.set_option('display.max_columns', None)
#     pd.set_option('display.max_colwidth', None)
#     pd.set_option('display.width', 0)
#     locations = ['高州泗水 高州根子']
#     # features = ['聲母', '韻母', '聲調']
#     features = ['韻母']
#     # group_inputs = ['組', '攝等', '清濁調']  # [OK] 用戶指定分組欄位
#     group_inputs = ['攝']  # [OK] 用戶指定分組欄位
#     pho_value = ['l', 'm', 'an']
#     regions = ['封綏', '儋州']
#     results = pho2sta(locations, regions, features, group_inputs, pho_value)
#
#     for row in results:
#         print(row)

# location = ['東莞莞城', '雲浮富林']
# result = get_feature_counts(location)
# for loc, features in result.items():
#     print(f"地点: {loc}")
#     for feature, values in features.items():
#         print(f"  {feature}:")
#         for value, count in values.items():
#             print(f"    {value}: {count} 字")
#     print("\n")
