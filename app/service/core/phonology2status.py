import re

import pandas as pd
from fastapi import HTTPException

from app.common.path import QUERY_DB_USER, DIALECTS_DB_USER, CHARACTERS_DB_PATH
from app.service.core.matrix import MERGE_MAP
from app.service.core.process_sp_input import split_pho_input
from app.common.constants import (
    AMBIG_VALUES, HIERARCHY_COLUMNS, s2t_column,
    POLYPHONIC_MARKS, WENDU_MARKS, BAIDU_MARKS,
)
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


def _mark_to_text(value) -> str:
    return "" if value is None else str(value).strip()


def _is_polyphonic_mark(value) -> bool:
    return _mark_to_text(value) in POLYPHONIC_MARKS


def _is_wendu_mark(value) -> bool:
    return _mark_to_text(value) in WENDU_MARKS


def _is_baidu_mark(value) -> bool:
    return _mark_to_text(value) in BAIDU_MARKS


def query_dialect_features(locations, features, db_path=DIALECTS_DB_USER, table="dialects", feature_value_filter=None):
    if not locations or not features:
        return {}
    allowed_features = {"聲母", "韻母", "聲調"}
    features = [f for f in features if f in allowed_features]
    if not features:
        return {}
    """
    從 dialects 數據庫中查出指定地點與特徵（如聲母、韻母等）對應的漢字。

    性能优化：使用SQL层面的GROUP BY代替pandas处理（5-10倍性能提升）
    可選地按 feature_value_filter 只構建命中的 bucket；未提供時保持原行為。
    """
    pool = get_db_pool(db_path)
    result = {}
    feature_value_filter = feature_value_filter or {}

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
            allowed_values = feature_value_filter.get(feature)

            # 使用字典进行分组（代替pandas groupby）
            from collections import defaultdict
            groups = defaultdict(list)

            for row in all_rows:
                feature_value = row[feature_idx]
                if not feature_value:  # 跳过NULL值
                    continue
                if allowed_values is not None and feature_value not in allowed_values:
                    continue
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

                # 处理多音字 / 文白读
                poly_dict = defaultdict(set)
                wendu_dict = defaultdict(set)
                baidu_dict = defaultdict(set)
                for row in rows:
                    mark = row[col_indices['多音字']]
                    hz = row[col_indices['漢字']]
                    pron = row[col_indices['音節']]
                    if not pron:
                        continue
                    if _is_polyphonic_mark(mark):
                        poly_dict[hz].add(pron)
                    if _is_wendu_mark(mark):
                        wendu_dict[hz].add(pron)
                    if _is_baidu_mark(mark):
                        baidu_dict[hz].add(pron)

                poly_details = [f"{hz}:{';'.join(sorted(prons))}" for hz, prons in poly_dict.items()]
                wendu_details = [f"{hz}:{';'.join(sorted(prons))}" for hz, prons in wendu_dict.items()]
                baidu_details = [f"{hz}:{';'.join(sorted(prons))}" for hz, prons in baidu_dict.items()]
                wendu_details_map = {hz: ';'.join(sorted(prons)) for hz, prons in wendu_dict.items()}
                baidu_details_map = {hz: ';'.join(sorted(prons)) for hz, prons in baidu_dict.items()}

                feature_payload = {
                    "漢字": chars,
                    "sub_df": sub_df,
                    "多音字詳情": poly_details
                }
                if wendu_details:
                    feature_payload["文讀詳情"] = wendu_details
                if baidu_details:
                    feature_payload["白讀詳情"] = baidu_details
                if wendu_details_map:
                    feature_payload["文讀詳情map"] = wendu_details_map
                if baidu_details_map:
                    feature_payload["白讀詳情map"] = baidu_details_map

                feature_dict[feature_value] = feature_payload

            result[feature] = feature_dict

    return result


def query_dialect_feature_values(locations, features, pho_values=None, db_path=DIALECTS_DB_USER, table="dialects"):
    if not locations or not features:
        return {}
    allowed_features = {"聲母", "韻母", "聲調"}
    features = [f for f in features if f in allowed_features]
    if not features:
        return {}

    pho_values = split_pho_input(pho_values or [])
    if not pho_values:
        return {}

    pool = get_db_pool(db_path)
    matched_values = {feature: set() for feature in features}

    with pool.get_connection() as conn:
        cursor = conn.cursor()
        query = f"SELECT {', '.join(features)} FROM {table} WHERE 簡稱 IN ({','.join(['?'] * len(locations))})"
        cursor.execute(query, locations)
        all_rows = cursor.fetchall()

        for row in all_rows:
            for idx, feature in enumerate(features):
                feature_value = row[idx]
                if not feature_value:
                    continue
                for pho_value in pho_values:
                    if any('\u4e00' <= char <= '\u9fff' for char in pho_value):
                        if re.search(pho_value, feature_value):
                            matched_values[feature].add(feature_value)
                            break
                    else:
                        if feature_value == pho_value:
                            matched_values[feature].add(feature_value)
                            break

    return matched_values


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
        table="characters",
        char_row_map=None,
        ordered_char_rows=None,
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

    if char_df.empty:
        return pd.DataFrame()

    if char_row_map is not None:
        row_indexes = []
        seen_indexes = set()
        source_chars = ordered_char_rows if ordered_char_rows is not None else char_list
        for hz in source_chars:
            for idx in char_row_map.get(hz, []):
                if idx not in seen_indexes:
                    seen_indexes.add(idx)
                    row_indexes.append(idx)
        if not row_indexes:
            return pd.DataFrame()
        working_df = char_df.loc[row_indexes].copy()
    else:
        working_df = char_df[char_df["漢字"].isin(char_list)].copy()
    if working_df.empty:
        return pd.DataFrame()

    multi_status_col = schema.get("multi_status_column", "多地位標記")
    multi_cols_groups = schema.get("multi_status_cols", [["攝", "呼", "等", "韻", "調"], ["部位", "方式", "母"]])
    all_multi_cols = [c for grp in multi_cols_groups for c in grp]

    for col in all_multi_cols + [multi_status_col]:
        if col not in working_df.columns:
            working_df[col] = None

    total_chars = len(set(sub_df["漢字"]))
    grouped_result = []

    working_df = working_df.dropna(subset=group_fields)
    if working_df.empty:
        return pd.DataFrame()

    grouped = working_df.groupby(group_fields)

    for group_keys, group_df in grouped:
        if not isinstance(group_keys, tuple):
            group_keys = (group_keys,)

        value_parts = []
        for field, val in zip(group_fields, group_keys):
            if val in ambig:
                suffix = suffix_map.get(field)
                if suffix:
                    val = f"{val}{suffix}"
            value_parts.append(val)
        group_value = "·".join(value_parts)

        unique_chars = group_df["漢字"].unique().tolist()
        count = len(unique_chars)

        poly_details = []
        poly_chars = group_df[group_df[multi_status_col] == "1"]["漢字"].unique()
        for hz in poly_chars:
            sub = working_df[(working_df["漢字"] == hz) & (working_df[multi_status_col] == "1")]
            summary = []
            for _, row in sub.iterrows():
                group_strs = []
                for grp in multi_cols_groups:
                    vals = [str(row[c]) for c in grp if pd.notna(row.get(c))]
                    group_strs.append("·".join(vals))
                summary.append(",".join(s for s in group_strs if s))
            poly_details.append(f"{hz}: {' | '.join(summary)}")

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

    normalized_group_inputs = [
        convert_simplified_to_traditional(item)
        for item in (status_inputs or [])
        if item
    ]

    grouping_columns_map = {}
    for feature in features:
        if normalized_group_inputs:
            print(f"[OK] 特徵【{feature}】使用分組欄位：{normalized_group_inputs}")
            grouping_columns_map[feature] = normalized_group_inputs
        else:
            print(f"[X] 未提供 group_inputs，特徵【{feature}】將使用預設分組欄位")
            grouping_columns_map[feature] = None

    locations_new = query_dialect_abbreviations(regions, locations, db_path=query_db_path, region_mode=region_mode)
    match_results = match_locations_batch_exact(" ".join(locations_new))
    if not any(res[1] == 1 for res in match_results):
        # print("🛑 沒有任何地點完全匹配，終止分析。")
        raise HTTPException(status_code=400, detail="🛑 沒有任何地點完全匹配，終止分析。")
        # return []

    unique_abbrs = list({abbr for res in match_results for abbr in res[0]})
    # print(f"\n📍 確認匹配地點：{unique_abbrs}")

    matched_feature_values = query_dialect_feature_values(
        unique_abbrs,
        features,
        pho_values=pho_values,
        db_path=dialect_db_path,
    ) if pho_values else {}

    feature_value_filter = {
        feature: values if values else None
        for feature, values in matched_feature_values.items()
    }
    if not feature_value_filter:
        feature_value_filter = None

    # 【性能优化】批量查询 characters.db（一次查询代替 N 次查询）
    dialect_output = query_dialect_features(
        unique_abbrs,
        features,
        db_path=dialect_db_path,
        feature_value_filter=feature_value_filter,
    )

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

    char_row_map = {}
    if not all_chars_df.empty:
        reset_df = all_chars_df.reset_index(drop=True)
        all_chars_df = reset_df
        for idx, hz in enumerate(all_chars_df["漢字"].tolist()):
            char_row_map.setdefault(hz, []).append(idx)

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
                matched_values = matched_feature_values.get(feature) or set()
                for fv, d in feature_items:
                    if fv in matched_values:
                        filtered_items.append((fv, d))

                if filtered_items:
                    feature_items = filtered_items
                else:
                    print("     [!] 無匹配特徵值，fallback 使用全部")

            for feature_value, data in feature_items:
                sub_df = data["sub_df"]
                ordered_loc_chars = sub_df[sub_df["簡稱"] == loc]["漢字"].drop_duplicates().tolist()
                loc_chars = ordered_loc_chars
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
                    char_row_map=char_row_map,
                    ordered_char_rows=ordered_loc_chars,
                )

                wendu_map = data.get("文讀詳情map")
                if wendu_map is None:
                    wendu_map = {}
                    for detail in data.get("文讀詳情") or []:
                        if ":" in detail:
                            hz, value = detail.split(":", 1)
                            wendu_map[hz] = value
                baidu_map = data.get("白讀詳情map")
                if baidu_map is None:
                    baidu_map = {}
                    for detail in data.get("白讀詳情") or []:
                        if ":" in detail:
                            hz, value = detail.split(":", 1)
                            baidu_map[hz] = value

                def _filter_details_for_chars(chars):
                    current_chars = set(chars or [])
                    filtered = {}
                    if wendu_map:
                        filtered_wendu = [f"{hz}:{wendu_map[hz]}" for hz in current_chars if hz in wendu_map]
                        if filtered_wendu:
                            filtered["文讀詳情"] = filtered_wendu
                    if baidu_map:
                        filtered_baidu = [f"{hz}:{baidu_map[hz]}" for hz in current_chars if hz in baidu_map]
                        if filtered_baidu:
                            filtered["白讀詳情"] = filtered_baidu
                    return filtered

                if isinstance(result, list):
                    for item in result:
                        item.update(_filter_details_for_chars(item.get("對應字")))
                    results.extend(result)
                elif isinstance(result, pd.DataFrame):
                    result = result.copy()
                    result["文讀詳情"] = result["對應字"].apply(
                        lambda chars: _filter_details_for_chars(chars).get("文讀詳情")
                    )
                    result["白讀詳情"] = result["對應字"].apply(
                        lambda chars: _filter_details_for_chars(chars).get("白讀詳情")
                    )
                    results.append(result)
                else:
                    results.append(result)

    return results

# if __name__ == "__main__":
#     pd.set_option('display.max_rows', None)
#     pd.set_option('display.max_columns', None)
#     pd.set_option('display.max_colwidth', None)
#     pd.set_option('display.width', 0)
#     locations = ['高州泗水 高州根子']
#     # features = ['聲母', '韻母', '聲調']
#     features = ['韻母']
#     status_inputs = ['果']
#     group_inputs = ['攝']
#     # pho_values = ['m', 'ŋ']
#     # pho_values = ['an', 'uɐt']
#     # results = pho2sta(locations, regions, features, group_inputs, pho_values)
#     results = pho2sta(locations, features, status_inputs, pho_values=['i'],
#                      # query_db_path='../data/query.db',
#                      dialect_db_path='../data/dialects.db',
#                      # char_db_path='../data/characters.db',
#                      region_mode='yindian')
#     # results = pd.DataFrame(results)
#     print(results)
#     # print(results[['地點', '特徵類別', '特徵值','分組值', '字數', '佔比', '對應字']].to_string(index=False))
