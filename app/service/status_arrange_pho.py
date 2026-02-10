import re

import pandas as pd
from fastapi import HTTPException

from common.path import QUERY_DB_USER, DIALECTS_DB_USER, CHARACTERS_DB_PATH
from common.constants import HIERARCHY_COLUMNS, AMBIG_VALUES
from app.service.process_sp_input import auto_convert_batch
from app.service.getloc_by_name_region import query_dialect_abbreviations
from app.service.match_input_tip import match_locations_batch
from app.sql.db_pool import get_db_pool

"""
本腳本提供一組函數用於從語音描述詞查詢對應漢字，並根據不同地點與語音特徵進行統計分析。
核心流程與功能如下：

1. run_status：
   ➤ 將使用者輸入（如「知組三」）解析為篩選語法並查詢 characters.db，回傳漢字與多地位字。

2. query_characters_by_path：
   ➤ 解析 [值]{欄位} 語法，執行資料庫查詢並判定多地位。

3. query_by_status：
   ➤ 根據查得漢字，在指定地點與語音特徵下計算統計資訊與多音字詳情。

4. run_feature_analysis：
   ➤ 整合 run_status 與 query_by_status，批次處理多組輸入與地點，進行完整分析流程。

"""


def query_characters_by_path(path_string, db_path=CHARACTERS_DB_PATH, table="characters", exclude_columns=None):
    """
    📌 根據用戶輸入語法（如 "[知]{組}[三]{等}"）從 characters.db 中查出符合條件的漢字。

    功能包含：
    - 解析語法中指定的「欄位 + 值」條件
    - 根據條件篩選出符合的漢字
    - 額外分析這些字是否為「多地位」字（即一字多個音系地位）
    - 支持過濾多音多義字（通過 exclude_columns 參數）

    Args:
        exclude_columns: List[str] or None, 例如 ["多地位標記", "多等"]
                        用於過濾掉這些列值為 1（字符串或整數）的行

    回傳：
    - 符合條件的漢字清單
    - 多地位的漢字清單
    """

    # print(f"\n📥 查詢語法輸入：{path_string}")

    # 解析語法：[值]{欄位}
    pattern = r"\[([^\[\]]+)\]\{([^\{\}]+)\}"
    matches = re.findall(pattern, path_string)

    if not matches:
        print("[X] 無法解析輸入語法。請使用 [值]{欄位} 的格式")
        return [], []

    # print(f"[SEARCH] 解析出的條件：{matches}")

    filter_columns = [col for _, col in matches]
    for col in filter_columns:
        if col not in HIERARCHY_COLUMNS:
            print(f"[!] 欄位「{col}」不在允許的層級欄位中")
            return [], []

    # 使用連接池
    pool = get_db_pool(db_path)
    with pool.get_connection() as conn:
        # --- [RUN] 優化開始：動態組裝更高效的 SQL ---
        conditions = []
        params = []

        for val, col in matches:
            # 針對「等=三」的特殊處理：使用 SQL 的 IN 語法
            if col == "等" and val == "三":
                conditions.append(f"{col} IN (?, ?, ?, ?)")
                params.extend(["三A", "三B", "三C", "三銳"])
            else:
                conditions.append(f"{col} = ?")
                params.append(val)

        where_clause = " AND ".join(conditions)
        query = f"SELECT * FROM {table} WHERE {where_clause}"

        # 只執行一次查詢
        df = pd.read_sql_query(query, conn, params=params)
    # --- [RUN] 優化結束 ---

    # 【新增】應用過濾邏輯
    if exclude_columns:
        for col_name in exclude_columns:
            if col_name in df.columns:
                # 過濾掉該列值為 1（字符串或整數）的行
                df = df[
                    (df[col_name] != 1) &
                    (df[col_name] != "1")
                ]

    # [!] 原本這裡的 Python for 迴圈篩選是多餘的，因為 SQL 已經做完了，直接移除。
    # filtered_df 就是 df
    filtered_df = df

    if filtered_df.empty:
        return [], []

    # 提取漢字
    if "漢字" not in filtered_df.columns:
        print("[X] 缺少「漢字」欄")
        return [], []

    characters = filtered_df["漢字"].dropna().tolist()
    # print(f"\n[->] 符合條件的漢字共 {len(characters)} 個")

    # 多地位過濾
    multi_chars = []
    if "多地位標記" in filtered_df.columns:
        candidates = filtered_df[
            filtered_df["多地位標記"] == "1"
            ]["漢字"].dropna().unique().tolist()
        # print(f"🟡 初步多地位標記候選：{len(candidates)} 字")

        for word in candidates:
            # 這裡邏輯保持不變：檢查該字在當前篩選結果中是否有多個條目
            all_rows = df[df["漢字"] == word]
            sub = all_rows[filter_columns].drop_duplicates()
            if len(sub) > 1:
                multi_chars.append(word)
        # print(f"🟠 經過比對後確定有多地位的漢字：{len(multi_chars)} 字")
    else:
        print("[!] 無「多地位標記」欄")

    return characters, multi_chars


def query_by_status(char_list, locations, features, user_input, db_path=DIALECTS_DB_USER, table="dialects"):
    """
    📌 根據提供的漢字名單，查詢其在不同地點與語音特徵（如聲母/韻母）下的分佈情況。

    功能包含：
    - 從 dialects.db 中找出指定地點與漢字的資料
    - 計算每種語音特徵值（如 b, p, m...）的字數、比例（去重後）
    - 處理「多音字」的詳細音節資訊（保留所有對應的發音）
    - 輸出欄位包含：分組值（特徵=值）

    回傳：
    - 每筆統計結果以字典方式輸出，最終轉為 DataFrame
    """
    # print(f"[PKG] 連接資料庫：{db_path}")
    pool = get_db_pool(db_path)
    with pool.get_connection() as conn:
        # 1. 只選擇需要的欄位並添加過濾條件，減少資料庫加載量
        query = f"""
        SELECT 簡稱, 漢字, {', '.join(features)}, 多音字, 音節
        FROM {table}
        WHERE 簡稱 IN ({','.join(f"'{loc}'" for loc in locations)})
        AND 漢字 IN ({','.join(f"'{char}'" for char in char_list)})
        """
        try:
            df = pd.read_sql_query(query, conn)
            print(f"[OK] 查詢結果：載入 {len(df)} 條資料")
        except Exception as e:
            print(f"[X] 查詢失敗：{e}")

    # 2. 为每个地点分别查询多音字资料，并构建多音字字典
    poly_dicts = {}  # 存儲每個地點的多音字字典
    for loc in locations:
        # 針對每個地點進行查詢
        # print(f"[SEARCH] 查詢地點：{loc}")
        pool_poly = get_db_pool(db_path)
        with pool_poly.get_connection() as conn_poly:
            try:
                # 查詢該地點的多音字資料
                query = f"""
                SELECT 漢字, 音節
                FROM {table}
                WHERE 多音字 = '1'
                AND 簡稱 = '{loc}'
                AND 漢字 IN ({','.join(f"'{char}'" for char in char_list)})
                """
                poly_data = pd.read_sql_query(query, conn_poly)
                # print(f"[OK] 地點 {loc} 的多音字資料載入完成，共 {len(poly_data)} 條")
            except Exception as e:
                print(f"[X] 查詢地點 {loc} 的多音字資料失敗：{e}")

        # 構建該地點的多音字字典
        poly_dict = poly_data.groupby("漢字")["音節"].apply(lambda x: '|'.join(x)).to_dict()
        poly_dicts[loc] = poly_dict
        # print(f"[OK] 地點 {loc} 的多音字字典建構完成，共 {len(poly_dict)} 條")

    # 3. 開始處理資料
    results = []

    # print("[SEARCH] 開始處理地點和特徵...")

    for loc in locations:
        # print(f"\n[SEARCH] 處理地點：{loc}")
        loc_df = df[df["簡稱"] == loc]
        # print(f"   - 該地資料筆數：{len(loc_df)}")

        loc_chars_df = loc_df[loc_df["漢字"].isin(char_list)]
        # print(f"   - 匹配輸入漢字筆數：{len(loc_chars_df)} / {len(char_list)}")

        if loc_chars_df.empty:
            print("   [!] 無符合漢字，略過此地點")
            results.append({
                "地點": loc,
                "特徵類別": "無",
                "特徵值": "無",
                "分組值": {},
                "字數": 0,
                "佔比": 0.0,
                "對應字": [],
                "多音字詳情": "[X] 無符合漢字"
            })
            continue

        total_chars = len(loc_chars_df["漢字"].unique())
        # print(f"   - 總共字數：{total_chars}")

        for feature in features:
            # print(f"   🔎 處理特徵：{feature}")
            feature_groups = loc_chars_df.groupby(feature)

            for fval, sub_df in feature_groups:
                all_chars = sub_df["漢字"].tolist()
                unique_chars = list(set(all_chars))
                count = len(unique_chars)

                # print(f"     ▶︎ {feature} = {fval}，字數：{count}，字例：{unique_chars[:5]}...")

                poly_details = []
                # 使用該地點的多音字字典
                poly_dict = poly_dicts.get(loc, {})
                for hz in unique_chars:
                    if hz in poly_dict:
                        poly_details.append(f"{hz}:{poly_dict[hz]}")

                results.append({
                    "地點": loc,
                    "特徵類別": feature,
                    "特徵值": user_input,
                    "分組值": {user_input: fval},
                    "字數": count,
                    "佔比": round(count / total_chars, 4) if total_chars else 0.0,
                    "對應字": unique_chars,
                    "多音字詳情": "; ".join(poly_details) if poly_details else ""
                })

    # print("\n[OK] 分析完成！")

    # 返回結果
    return pd.DataFrame(results)

def convert_path_str(path_str: str) -> str:
        """
        將格式 [莊]{組}[宕]{攝} 轉換為：
        - 若值在 AMBIG_VALUES 中（有歧義），保留 {欄位} → 莊組
        - 否則只保留值 → 宕
        最終以 - 串接
        """
        items = re.findall(r'[\[\{](.*?)[\]\}]', path_str)
        pairs = []
        for i in range(0, len(items), 2):
            val, col = items[i], items[i + 1]
            if val in AMBIG_VALUES:
                pairs.append(val + col)
            else:
                pairs.append(val)
        return '·'.join(pairs)

def run_status(
        input_strings,
        db_path=CHARACTERS_DB_PATH,
        table="characters",
):
    """
           📌 功能總結：

       🔹 主要用途：
       接收一組語音條件輸入字串（如「知組三」、「蟹攝」），
       將其轉換為一個或多個標準查詢語法（path），並查詢符合條件的漢字。

       🔁 每個條件輸入可能會對應到多個 path（如等級、組、攝的展開），
       本函數會對每個 path 獨立查詢，再將結果合併返回。

       ✔ 處理流程：
       1. 調用 `auto_convert_batch(s)` 將每個輸入轉換為多個 path（如 [知]{組}-[三]{等}）
       2. 每個 path 用 `query_characters_by_path()` 查出符合的漢字與多地位字
       3. 最後將每個輸入的所有 path 查得的字與多地位字合併
       4. 回傳格式保留與舊版本一致，以支援原先 `sta2pho` 用法

       🧾 回傳內容：
       - List，每個元素為一個 tuple：
           (
               原始輸入字串,           # 例如 "蟹攝"
               合併後的漢字清單,       # e.g., ["協", "些", "斜"]
               合併後的多地位字清單,   # e.g., ["協"]
               每個 path 的明細清單     # list of dicts（含 path、characters、multi）
           )
    """
    results_summary = []

    for s in input_strings:
        if "-" in s:
            # ➤ 保留原邏輯：含有破折號，直接處理整體
            batch_result = auto_convert_batch(s)

            if not isinstance(batch_result, list):
                results_summary.append((s, False, False))
                print(f"  [X] 無法處理（非 list 結果）：{s}")
                continue

            has_error = any(
                isinstance(r, tuple) and r[0] is False for r in batch_result
            )

            path_results = []

            for path_tuple in batch_result:
                if isinstance(path_tuple, tuple) and path_tuple[0] is not False:
                    path_str = path_tuple[0]
                    characters, multi_chars = query_characters_by_path(
                        path_str, db_path=db_path, table=table
                    )
                    # simplified_input = ''.join(re.findall(r'\[(.*?)\]', path_str))
                    simplified_input = convert_path_str(path_str)
                    # print(f"path_str0{path_str}")
                    # print(f"simpilfied0_input{simplified_input}")
                    path_results.append({
                        "path": simplified_input,
                        "characters": characters,
                        "multi": multi_chars
                    })

            if path_results:
                all_chars = []
                all_multi = []
                for result in path_results:
                    all_chars.extend(result["characters"])
                    all_multi.extend(result["multi"])
                results_summary.append((s, all_chars, list(set(all_multi)), path_results))
            else:
                results_summary.append((s, False, False, []))

            if has_error:
                print(f"  [!] 部分片段轉換失敗：{s}")

        elif " " in s:
            # ➤ 不含破折號但有空格：多段合併處理
            parts = s.split()
            all_chars = []
            all_multi = []
            has_error = False

            for part in parts:
                batch_result = auto_convert_batch(part)

                if not isinstance(batch_result, list):
                    has_error = True
                    continue

                if any(isinstance(r, tuple) and r[0] is False for r in batch_result):
                    has_error = True

                for path_tuple in batch_result:
                    if isinstance(path_tuple, tuple) and path_tuple[0] is not False:
                        path_str = path_tuple[0]
                        characters, multi_chars = query_characters_by_path(
                            path_str, db_path=db_path, table=table
                        )
                        all_chars.extend(characters)
                        all_multi.extend(multi_chars)
            # print(f"s{s}")
            if all_chars:
                results_summary.append((
                    s,
                    all_chars,
                    list(set(all_multi)),
                    [{
                        "path": s,
                        "characters": all_chars,
                        "multi": list(set(all_multi))
                    }]
                ))
            else:
                results_summary.append((s, False, False, []))

            if has_error:
                print(f"  [!] 部分片段轉換失敗：{s}")

        else:
            # ➤ 單段處理（無破折號、無空格）
            batch_result = auto_convert_batch(s)

            if not isinstance(batch_result, list):
                results_summary.append((s, False, False))
                print(f"  [X] 無法處理（非 list 結果）：{s}")
                continue

            has_error = any(
                isinstance(r, tuple) and r[0] is False for r in batch_result
            )

            path_results = []

            for path_tuple in batch_result:
                if isinstance(path_tuple, tuple) and path_tuple[0] is not False:
                    path_str = path_tuple[0]
                    characters, multi_chars = query_characters_by_path(
                        path_str, db_path=db_path, table=table
                    )
                    # simplified_input = ''.join(re.findall(r'\[(.*?)\]', path_str))
                    simplified_input = convert_path_str(path_str)
                    # print(f"path_str{path_str}")
                    # print(f"simpilfied_input{simplified_input}")
                    path_results.append({
                        "path": simplified_input,
                        "characters": characters,
                        "multi": multi_chars
                    })

            if path_results:
                all_chars = []
                all_multi = []
                for result in path_results:
                    all_chars.extend(result["characters"])
                    all_multi.extend(result["multi"])
                results_summary.append((s, all_chars, list(set(all_multi)), path_results))
            else:
                results_summary.append((s, False, False, []))

            if has_error:
                print(f"  [!] 部分片段轉換失敗：{s}")

    return results_summary


def sta2pho(
        locations,
        regions,
        features,
        test_inputs,
        db_path_char=CHARACTERS_DB_PATH,
        db_path_dialect=DIALECTS_DB_USER,
        region_mode='yindian',
        db_path_query=QUERY_DB_USER  # 新增：用于查询地点的数据库
):
    """
    📌 主控函數：對語音條件輸入進行特徵分析，支援多地點與特徵欄位。
    回傳：List of DataFrames（每個條件的統計結果）

    Args:
        db_path_dialect: 方言数据库路径（用于查询实际读音数据）
        db_path_query: 查询数据库路径（用于查询地点信息）
    """
    locations_new = query_dialect_abbreviations(regions, locations, db_path=db_path_query, region_mode=region_mode)
    match_results = match_locations_batch(" ".join(locations_new))
    if not any(res[1] == 1 for res in match_results):
        raise HTTPException(status_code=400, detail="🛑 沒有任何地點完全匹配，終止分析。")
        # print("🛑 沒有任何地點完全匹配，終止分析。")
        # return []

    unique_abbrs = list({abbr for res in match_results for abbr in res[0]})
    # print(f"\n📍 完全匹配地點簡稱：{unique_abbrs}")

    if not test_inputs:
        print("[i] inputs 為空，自動推導條件字串...")
        pool = get_db_pool(db_path_char)
        with pool.get_connection() as conn:
            df_char = pd.read_sql_query("SELECT * FROM characters", conn)

        auto_inputs = []
        auto_features = []

        for feat in features:
            if feat == "聲母":
                unique_vals = sorted(df_char["母"].dropna().unique())
                auto_inputs.extend([f"{v}母" for v in unique_vals])
                auto_features.extend(["聲母"] * len(unique_vals))

            elif feat == "韻母":
                unique_vals = sorted(df_char["攝"].dropna().unique())
                auto_inputs.extend([f"{v}攝" for v in unique_vals])
                auto_features.extend(["韻母"] * len(unique_vals))

            elif feat == "聲調":
                clean_vals = sorted(df_char["清濁"].dropna().unique())
                tone_vals = sorted(df_char["調"].dropna().unique())
                for cv in clean_vals:
                    for tv in tone_vals:
                        auto_inputs.append(f"{cv}{tv}")
                        auto_features.append("聲調")

            else:
                print(f"[!] 未支持的特徵類型：{feat}，略過")

        test_inputs = auto_inputs
        features = auto_features
        # print(test_inputs)
        # print(f"[FIX] 產生輸入條件 {len(test_inputs)} 筆 ➤ 前5項：{test_inputs[:5]}")

    all_results = []

    if len(features) == 1:
        for user_input in test_inputs:
            print("\n" + "═" * 60)
            # print(f"📘📘 分析輸入：{user_input} 對應特徵：{features[0]}")

            summary = run_status([user_input], db_path=db_path_char)
            # if not summary[1]:  # 这里检查 summary 中第二个元素
            #     raise HTTPException(status_code=404, detail="[X] 輸入的中古地位不存在")

            for path_input, chars, multi, path_details in summary:
                if chars is False:
                    print("🛑 查詢失敗或無法解析")
                    continue

                for result in path_details:
                    path_str = result["path"]
                    path_chars = result["characters"]

                    if not path_chars:
                        continue

                    # print(f"\n[FIX] 開始分析『{path_str}』的特徵分布 ({features[0]})...\n")
                    # simplified_input = ''.join(re.findall(r'\[(.*?)\]', path_str))
                    df = query_by_status(path_chars, unique_abbrs, [features[0]], path_str,
                                         db_path=db_path_dialect)

                    all_results.append(df)

    else:
        for user_input, feature in zip(test_inputs, features):
            # print(f"\n📘 分析輸入：{user_input} 對應特徵：{feature}")

            summary = run_status([user_input], db_path=db_path_char)
            # if not summary[1]:  # 这里检查 summary 中第二个元素
            #     raise HTTPException(status_code=404, detail="[X] 輸入的中古地位不存在")

            for path_input, chars, multi, path_details in summary:
                if chars is False:
                    print("🛑 查詢失敗或無法解析")
                    continue

                for result in path_details:
                    path_str = result["path"]
                    path_chars = result["characters"]

                    if not path_chars:
                        continue

                    # print(f"\n[FIX] 開始分析『{path_str}』的特徵分布 ({feature})...\n")
                    # simplified_input = ''.join(re.findall(r'\[(.*?)\]', path_str))
                    df = query_by_status(path_chars, unique_abbrs, [feature], path_str, db_path=db_path_dialect)

                    all_results.append(df)

    return all_results


# 這函數沒啥用
def extract_unique_values(db_path=CHARACTERS_DB_PATH, table="characters"):
    pool = get_db_pool(db_path)
    with pool.get_connection() as conn:
        df = pd.read_sql_query(f"SELECT * FROM {table}", conn)

    unique_values = {}

    for col in HIERARCHY_COLUMNS:
        if col in df.columns:
            values = df[col].dropna().unique()
            values = sorted(str(v).strip() for v in values if str(v).strip() != "")
            unique_values[col] = values
        else:
            unique_values[col] = []
            print(f"[!] 欄位「{col}」不存在")

    return unique_values


# if __name__ == "__main__":
#     pd.set_option('display.max_rows', None)
#     pd.set_option('display.max_columns', None)
#     pd.set_option('display.max_colwidth', None)
#     pd.set_option('display.width', 0)
#
    # status_inputs = ["蟹-系等", "知組三 端", "通开三"]
    # # status_inputs = ["蟹-等"]
    # locations = ['东莞莞城', '雲浮富林']
    # # features = ['聲母', '韻母', '聲調']
    # # regions = ['封綏', '儋州']
    # regions = [""]
    # features = ['聲母']
    #
    # results = sta2pho(locations, regions, features, status_inputs)
    # # print(all_summaries)
    #
    # for row in results:
    #     print(row)
# query_characters_by_path('[三]{等}')

