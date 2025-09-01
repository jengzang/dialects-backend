import re
import sqlite3

import pandas as pd
from fastapi import HTTPException

from common.config import CHARACTERS_DB_PATH, DIALECTS_DB_USER
from app.service.process_sp_input import split_pho_input
from common.constants import AMBIG_VALUES, HIERARCHY_COLUMNS, s2t_column
from common.getloc_by_name_region import query_dialect_abbreviations
from app.service.match_input_tip import match_locations_batch

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
    """
    從 dialects 數據庫中查出指定地點與特徵（如聲母、韻母等）對應的漢字。

    返回格式為：
    {
        '聲母': {
            'b': {
                '漢字': [...],
                'sub_df': 子表 DataFrame（含簡稱、漢字、特徵值、音節、是否多音字）,
                '多音字詳情': [hz1:pron1;pron2, hz2:pron1;pron2]
            },
            ...
        },
        '韻母': {
            ...
        }
    }
    """
    # 連接資料庫
    conn = sqlite3.connect(db_path)

    # 優化：只選擇需要的欄位並添加過濾條件
    query = f"""
    SELECT 簡稱, 漢字, {', '.join(features)}, 音節, 多音字
    FROM {table}
    WHERE 簡稱 IN ({','.join(f"'{loc}'" for loc in locations)})
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    result = {}

    # 針對每個特徵進行處理
    for feature in features:
        # 只保留該特徵的資料並丟棄缺失值
        sub_df = df[["簡稱", "漢字", feature, "音節", "多音字"]].dropna(subset=[feature])
        feature_dict = {}

        # 查詢每個特徵值的所有漢字
        for value in sorted(sub_df[feature].unique()):
            chars = sub_df[sub_df[feature] == value]["漢字"].unique().tolist()
            feature_dict[value] = {
                "漢字": chars,
                "sub_df": sub_df[(sub_df[feature] == value)],
                "多音字詳情": []
            }

            # 查詢多音字：只查詢多音字標註為 "1" 的資料
            poly_df = sub_df[(sub_df["多音字"] == "1") & (sub_df[feature] == value)]
            poly_dict = {}

            # 儲存該特徵下的所有多音字
            for hz in poly_df["漢字"].unique():
                poly_dict[hz] = poly_df[poly_df["漢字"] == hz]["音節"].unique().tolist()

            # 存儲多音字詳情
            for hz, pron_list in poly_dict.items():
                detail = f"{hz}:{';'.join(pron_list)}"
                feature_dict[value]["多音字詳情"].append(detail)

        result[feature] = feature_dict

    return result


def analyze_characters_from_db(
        char_list,
        feature_type,
        feature_value,
        loc,
        sub_df,
        char_db_path=CHARACTERS_DB_PATH,
        group_fields=None
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
    """

    default_grouping = {
        "聲母": ["母"],
        "韻母": ["攝"],
        "聲調": ["清濁", "調"]
    }
    # print(f"特徵值{feature_value}")
    if not group_fields:
        group_fields = default_grouping.get(feature_type)
        if not group_fields:
            raise ValueError(f"❌ 未定義的 feature_type：{feature_type}")

    conn = sqlite3.connect(char_db_path)
    placeholders = ','.join(['?'] * len(char_list))
    query = f"SELECT * FROM characters WHERE 漢字 IN ({placeholders})"
    df = pd.read_sql_query(query, conn, params=char_list)
    conn.close()

    for col in ["攝", "呼", "等", "韻", "調", "系", "組", "母", "多地位標記"]:
        if col not in df.columns:
            df[col] = None

    total_chars = len(set(sub_df["漢字"]))
    grouped_result = []

    df = df.dropna(subset=group_fields)
    grouped = df.groupby(group_fields)

    for group_keys, group_df in grouped:
        # 特定欄位需要後綴
        suffix_map = {
            "系": "系",
            "組": "組",
            "母": "母",
            "攝": "攝",
            "韻": "韻"
        }

        # 使用 group_df 中第一筆資料取得欄位值（若需要用到 row，可取樣一筆）
        _, sample_row = next(group_df.iterrows())

        # 建構 value（加後綴）
        value_parts = []
        for field, val in zip(group_fields, group_keys):
            if val in AMBIG_VALUES:
                suffix = suffix_map.get(field)
                if suffix:
                    val = f"{val}{suffix}"
            value_parts.append(val)
        group_value = "·".join(value_parts)

        # 最終的分組值格式
        # group_values = {group_key_label: group_value}
        group_values = {feature_value: group_value}

        # 以下原本的邏輯照舊
        unique_chars = group_df["漢字"].unique().tolist()
        count = len(unique_chars)

        poly_details = []
        poly_chars = group_df[group_df["多地位標記"] == "1"]["漢字"].unique()
        for hz in poly_chars:
            sub = df[(df["漢字"] == hz) & (df["多地位標記"] == "1")]
            summary = []
            for _, row in sub.iterrows():
                parts = f"{row['攝']}{row['呼']}{row['等']}{row['韻']}{row['調']}"
                meta = f"{row['系']}·{row['組']}·{row['母']}"
                summary.append(f"{parts},{meta}")
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


def pho2sta(locations, regions, features, status_inputs,
            pho_values=None,
            dialect_db_path=DIALECTS_DB_USER,
            character_db_path=CHARACTERS_DB_PATH, region_mode='yindian'):
    def convert_simplified_to_traditional(simplified_text):
        return "".join([s2t_column.get(ch, ch) for ch in simplified_text])

    pho_values = split_pho_input(pho_values or [])

    grouping_columns_map = {}
    for idx, feature in enumerate(features):
        user_input = status_inputs[idx] if idx < len(status_inputs) else ""

        # ✅ 最開始就做簡體轉繁體轉換
        user_input = convert_simplified_to_traditional(user_input)

        # 嘗試匹配欄位
        user_columns = [col for col in HIERARCHY_COLUMNS if col in user_input]

        if user_columns:
            print(f"✅ 特徵【{feature}】使用分組欄位：{user_columns}")
            grouping_columns_map[feature] = user_columns
        else:
            print(f"❌ 輸入「{user_input}」未匹配任何欄位，特徵【{feature}】將使用預設分組欄位")
            grouping_columns_map[feature] = None

    locations_new = query_dialect_abbreviations(regions, locations,region_mode=region_mode)
    match_results = match_locations_batch(" ".join(locations_new))
    if not any(res[1] == 1 for res in match_results):
        # print("🛑 沒有任何地點完全匹配，終止分析。")
        raise HTTPException(status_code=404, detail="🛑 沒有任何地點完全匹配，終止分析。")
        # return []

    unique_abbrs = list({abbr for res in match_results for abbr in res[0]})
    # print(f"\n📍 確認匹配地點：{unique_abbrs}")

    results = []
    dialect_output = query_dialect_features(unique_abbrs, features, db_path=dialect_db_path)

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
                    print("     ⚠️ 無匹配特徵值，fallback 使用全部")

            for feature_value, data in feature_items:
                sub_df = data["sub_df"]
                loc_chars = sub_df[sub_df["簡稱"] == loc]["漢字"].unique().tolist()
                # print(f"     ➤ 運算特徵值：{feature_value}（字數：{len(loc_chars)}）")

                if not loc_chars:
                    # print("        ⚠️ 該特徵值在此地點無資料，略過")
                    continue

                result = analyze_characters_from_db(
                    char_list=loc_chars,
                    feature_type=feature,
                    feature_value=feature_value,
                    loc=loc,
                    sub_df=sub_df[sub_df["簡稱"] == loc],
                    char_db_path=character_db_path,
                    group_fields=group_fields,
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
#     # group_inputs = ['組', '攝等', '清濁調']  # ✅ 用戶指定分組欄位
#     group_inputs = ['攝']  # ✅ 用戶指定分組欄位
#     pho_value = ['l', 'm', 'an']
#     regions = ['封綏', '儋州']
#     results = pho2sta(locations, regions, features, group_inputs, pho_value)
#
#     for row in results:
#         print(row)
