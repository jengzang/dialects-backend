import re
from collections import defaultdict

import pandas as pd
from fastapi import HTTPException

from app.common.path import QUERY_DB_USER, DIALECTS_DB_USER, CHARACTERS_DB_PATH
from app.service.process_sp_input import split_pho_input
from app.common.constants import AMBIG_VALUES, HIERARCHY_COLUMNS, s2t_column, custom_order
from app.service.getloc_by_name_region import query_dialect_abbreviations
from app.service.match_input_tip import match_locations_batch_exact
from app.sql.db_pool import get_db_pool

# IPA 符號合併映射表
MERGE_MAP = {}
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
    # 使用連接池
    pool = get_db_pool(db_path)
    with pool.get_connection() as conn:
        # 優化：只選擇需要的欄位並添加過濾條件
        query = f"""
        SELECT 簡稱, 漢字, {', '.join(features)}, 音節, 多音字
        FROM {table}
        WHERE 簡稱 IN ({','.join(f"'{loc}'" for loc in locations)})
        """
        df = pd.read_sql_query(query, conn)

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
        group_fields=None,
        exclude_columns=None
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
            raise ValueError(f"[X] 未定義的 feature_type：{feature_type}")

    pool = get_db_pool(char_db_path)
    with pool.get_connection() as conn:
        placeholders = ','.join(['?'] * len(char_list))
        query = f"SELECT * FROM characters WHERE 漢字 IN ({placeholders})"
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

    for col in ["攝", "韻", "等", "呼", "入", "清濁", "系", "組", "母", "調", "部位", "方式", "多地位標記"]:
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
                meta = f"{row['部位']}·{row['方式']}·{row['母']}"
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


def analyze_characters_from_cached_df(
        char_df,
        char_list,
        feature_type,
        feature_value,
        loc,
        sub_df,
        group_fields=None
):
    """
    使用缓存的 characters DataFrame 进行分析（性能优化版本）

    与 analyze_characters_from_db 功能相同，但不查询数据库，直接使用传入的 DataFrame

    Args:
        char_df: 已经查询好的 characters DataFrame（包含所有需要的汉字）
        char_list: 当前需要分析的汉字列表
        其他参数同 analyze_characters_from_db
    """
    default_grouping = {
        "聲母": ["母"],
        "韻母": ["攝"],
        "聲調": ["清濁", "調"]
    }

    if not group_fields:
        group_fields = default_grouping.get(feature_type)
        if not group_fields:
            raise ValueError(f"[X] 未定義的 feature_type：{feature_type}")

    # 从缓存的 DataFrame 中过滤出当前需要的汉字
    df = char_df[char_df["漢字"].isin(char_list)].copy()

    if df.empty:
        return []

    # 确保所有必需的列存在
    for col in ["攝", "韻", "等", "呼", "入", "清濁", "系", "組", "母", "調", "部位", "方式", "多地位標記"]:
        if col not in df.columns:
            df[col] = None

    total_chars = len(set(sub_df["漢字"]))
    grouped_result = []

    df = df.dropna(subset=group_fields)
    grouped = df.groupby(group_fields)

    for group_keys, group_df in grouped:
        suffix_map = {
            "系": "系",
            "組": "組",
            "母": "母",
            "攝": "攝",
            "韻": "韻"
        }

        _, sample_row = next(group_df.iterrows())

        value_parts = []
        for field, val in zip(group_fields, group_keys):
            if val in AMBIG_VALUES:
                suffix = suffix_map.get(field)
                if suffix:
                    val = f"{val}{suffix}"
            value_parts.append(val)
        group_value = "·".join(value_parts)

        group_values = {feature_value: group_value}

        unique_chars = group_df["漢字"].unique().tolist()
        count = len(unique_chars)

        poly_details = []
        poly_chars = group_df[group_df["多地位標記"] == "1"]["漢字"].unique()
        for hz in poly_chars:
            sub = df[(df["漢字"] == hz) & (df["多地位標記"] == "1")]
            summary = []
            for _, row in sub.iterrows():
                parts = f"{row['攝']}{row['呼']}{row['等']}{row['韻']}{row['調']}"
                meta = f"{row['部位']}·{row['方式']}·{row['母']}"
                summary.append(f"{parts},{meta}")
            poly_details.append(f"{hz}: {' | '.join(summary)}")

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
            character_db_path=CHARACTERS_DB_PATH, region_mode='yindian',
            exclude_columns=None,
            query_db_path=QUERY_DB_USER):  # 新增：用于查询地点的数据库
    def convert_simplified_to_traditional(simplified_text):
        return "".join([s2t_column.get(ch, ch) for ch in simplified_text])

    pho_values = split_pho_input(pho_values or [])

    grouping_columns_map = {}
    for idx, feature in enumerate(features):
        user_input = status_inputs[idx] if idx < len(status_inputs) else ""

        # [OK] 最開始就做簡體轉繁體轉換
        user_input = convert_simplified_to_traditional(user_input)

        # 嘗試匹配欄位
        user_columns = [col for col in HIERARCHY_COLUMNS if col in user_input]

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
            query = f"SELECT * FROM characters WHERE 漢字 IN ({placeholders})"
            all_chars_df = pd.read_sql_query(query, conn, params=list(all_chars))
            print(f"[OK] 批量查询 characters.db 完成，共 {len(all_chars_df)} 条记录")
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
                    group_fields=group_fields
                )

                results.extend(result if isinstance(result, list) else [result])

    return results


def get_feature_counts(locations, db_path=DIALECTS_DB_USER, table="dialects"):
    """
    优化版本：使用 UNION ALL 将三次表扫描合并为一次查询
    显著提升查询性能（3次扫描 → 1次扫描）

    [DEPRECATED - 2026-02-14]
    此函数已迁移到 app.service.feature_stats 模块。
    为保持向后兼容性，此函数暂时保留，但建议更新导入：

    旧的导入（已弃用）:
        from app.service.phonology2status import get_feature_counts

    新的导入（推荐）:
        from app.service.feature_stats import get_feature_counts

    此函数计划在 1-2 周后移除。
    """
    result = defaultdict(lambda: defaultdict(dict))

    pool = get_db_pool(db_path)
    with pool.get_connection() as conn:
        cursor = conn.cursor()

        # [OK] 优化：使用 UNION ALL 合并三个查询为一次表扫描
        placeholders = ','.join(['?' for _ in locations])

        query_combined = f"""
            SELECT 簡稱, '聲母' as feature_type, 聲母 as value, COUNT(DISTINCT 漢字) AS 字數
            FROM {table}
            WHERE 簡稱 IN ({placeholders})
            GROUP BY 簡稱, 聲母

            UNION ALL

            SELECT 簡稱, '韻母' as feature_type, 韻母 as value, COUNT(DISTINCT 漢字) AS 字數
            FROM {table}
            WHERE 簡稱 IN ({placeholders})
            GROUP BY 簡稱, 韻母

            UNION ALL

            SELECT 簡稱, '聲調' as feature_type, 聲調 as value, COUNT(DISTINCT 漢字) AS 字數
            FROM {table}
            WHERE 簡稱 IN ({placeholders})
            GROUP BY 簡稱, 聲調
        """

        # 执行合并后的查询（参数需要重复3次，对应3个WHERE子句）
        cursor.execute(query_combined, locations * 3)

        # 处理所有结果，按特征类型分离
        all_rows = cursor.fetchall()
        for row in all_rows:
            loc = row[0]
            feature_type = row[1]
            value = row[2]
            count = row[3]

            # 根据特征类型填充结果字典
            result[loc][feature_type][value] = count

    return result


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
    # 按地点分组的数据
    locations_data = defaultdict(lambda: {
        "matrix": defaultdict(lambda: defaultdict(lambda: defaultdict(list))),
        "initials": set(),
        "finals": set(),
        "tones": set()
    })

    pool = get_db_pool(db_path)
    with pool.get_connection() as conn:
        cursor = conn.cursor()

        # 构建查询语句
        if locations and len(locations) > 0:
            # 查询指定地点
            placeholders = ','.join(f"'{loc}'" for loc in locations)
            query = f"""
                SELECT 簡稱, 聲母, 韻母, 聲調, 漢字
                FROM {table}
                WHERE 簡稱 IN ({placeholders})
                ORDER BY 簡稱, 聲母, 韻母, 聲調
            """
        else:
            # 查询所有地点
            query = f"""
                SELECT 簡稱, 聲母, 韻母, 聲調, 漢字
                FROM {table}
                ORDER BY 簡稱, 聲母, 韻母, 聲調
            """

        cursor.execute(query)
        rows = cursor.fetchall()

        # 处理查询结果
        for row in rows:
            location = row[0]  # 地点
            initial = row[1]   # 声母
            final = row[2]     # 韵母
            tone = row[3]      # 声调
            char = row[4]      # 汉字

            # 跳过空值
            if not location or not initial or not final or not tone or not char:
                continue

            # 添加到该地点的矩阵
            loc_data = locations_data[location]
            loc_data["matrix"][initial][final][tone].append(char)

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