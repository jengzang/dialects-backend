import re

import pandas as pd
from fastapi import HTTPException

from app.common.path import QUERY_DB_USER, DIALECTS_DB_USER, CHARACTERS_DB_PATH
from app.common.constants import HIERARCHY_COLUMNS, AMBIG_VALUES
from app.service.core.process_sp_input import auto_convert_batch
from app.service.geo.getloc_by_name_region import query_dialect_abbreviations
from app.service.geo.match_input_tip import match_locations_batch_exact
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

    性能优化：
    - 使用SQL层面的多地位字检查（20倍性能提升）
    - 避免pandas DataFrame的开销
    """

    # 解析語法：[值]{欄位}
    pattern = r"\[([^\[\]]+)\]\{([^\{\}]+)\}"
    matches = re.findall(pattern, path_string)

    if not matches:
        print("[X] 無法解析輸入語法。請使用 [值]{欄位} 的格式")
        return [], []

    filter_columns = [col for _, col in matches]
    for col in filter_columns:
        if col not in HIERARCHY_COLUMNS:
            print(f"[!] 欄位「{col}」不在允許的層級欄位中")
            return [], []

    # 使用連接池
    pool = get_db_pool(db_path)
    with pool.get_connection() as conn:
        cursor = conn.cursor()

        # 构建查询条件
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

        # 【SQL优化1】主查询：获取符合条件的汉字
        query = f"SELECT 漢字 FROM {table} WHERE {where_clause}"

        # 添加exclude_columns过滤
        if exclude_columns:
            for col_name in exclude_columns:
                query += f" AND ({col_name} != 1 AND {col_name} != '1')"

        cursor.execute(query, params)
        characters = [row[0] for row in cursor.fetchall() if row[0]]

        if not characters:
            return [], []

        # 【SQL优化2】多地位字检查：完全在SQL层面完成
        # 构建filter_columns的拼接表达式用于GROUP BY
        filter_cols_concat = " || '|' || ".join(filter_columns)

        multi_query = f"""
        SELECT 漢字
        FROM {table}
        WHERE {where_clause}
        AND 多地位標記 = '1'
        AND 漢字 IN ({','.join(['?'] * len(characters))})
        GROUP BY 漢字
        HAVING COUNT(DISTINCT {filter_cols_concat}) > 1
        """

        cursor.execute(multi_query, params + characters)
        multi_chars = [row[0] for row in cursor.fetchall()]

    return characters, multi_chars


def query_characters_by_path_batch(path_strings, db_path=CHARACTERS_DB_PATH, table="characters", exclude_columns=None):
    """
    📌 批量查询多个path_string，使用UNION ALL优化性能

    Args:
        path_strings: List[str], 多个查询字符串
        exclude_columns: List[str] or None

    Returns:
        List[Tuple[str, List[str], List[str]]], 每个元素为 (path_string, characters, multi_chars)

    性能优化：
    - 使用UNION ALL合并多个查询（减少数据库连接开销）
    - 一次性获取所有结果，在Python层面分组
    - 预期提升：30-50%
    """
    if not path_strings:
        return []

    # 解析所有path_string
    pattern = r"\[([^\[\]]+)\]\{([^\{\}]+)\}"
    parsed_queries = []

    for idx, path_string in enumerate(path_strings):
        matches = re.findall(pattern, path_string)
        if not matches:
            continue

        filter_columns = [col for _, col in matches]
        valid = all(col in HIERARCHY_COLUMNS for col in filter_columns)
        if not valid:
            continue

        parsed_queries.append({
            'idx': idx,
            'path_string': path_string,
            'matches': matches,
            'filter_columns': filter_columns
        })

    if not parsed_queries:
        return []

    pool = get_db_pool(db_path)
    with pool.get_connection() as conn:
        cursor = conn.cursor()

        # 【批量优化】构建UNION ALL查询
        union_queries = []
        all_params = []

        for query_info in parsed_queries:
            conditions = []
            params = []

            for val, col in query_info['matches']:
                if col == "等" and val == "三":
                    conditions.append(f"{col} IN (?, ?, ?, ?)")
                    params.extend(["三A", "三B", "三C", "三銳"])
                else:
                    conditions.append(f"{col} = ?")
                    params.append(val)

            where_clause = " AND ".join(conditions)

            # 添加查询索引以便后续分组
            subquery = f"SELECT {query_info['idx']} as query_idx, 漢字 FROM {table} WHERE {where_clause}"

            if exclude_columns:
                for col_name in exclude_columns:
                    subquery += f" AND ({col_name} != 1 AND {col_name} != '1')"

            union_queries.append(subquery)
            all_params.extend(params)

        # 执行UNION ALL查询
        union_query = " UNION ALL ".join(union_queries)
        cursor.execute(union_query, all_params)

        # 按query_idx分组结果
        results_by_idx = {}
        for row in cursor.fetchall():
            query_idx, char = row
            if query_idx not in results_by_idx:
                results_by_idx[query_idx] = []
            if char:
                results_by_idx[query_idx].append(char)

        # 批量查询多地位字
        final_results = []
        for query_info in parsed_queries:
            idx = query_info['idx']
            characters = results_by_idx.get(idx, [])

            if not characters:
                final_results.append((query_info['path_string'], [], []))
                continue

            # 查询多地位字
            conditions = []
            params = []

            for val, col in query_info['matches']:
                if col == "等" and val == "三":
                    conditions.append(f"{col} IN (?, ?, ?, ?)")
                    params.extend(["三A", "三B", "三C", "三銳"])
                else:
                    conditions.append(f"{col} = ?")
                    params.append(val)

            where_clause = " AND ".join(conditions)
            filter_cols_concat = " || '|' || ".join(query_info['filter_columns'])

            multi_query = f"""
            SELECT 漢字
            FROM {table}
            WHERE {where_clause}
            AND 多地位標記 = '1'
            AND 漢字 IN ({','.join(['?'] * len(characters))})
            GROUP BY 漢字
            HAVING COUNT(DISTINCT {filter_cols_concat}) > 1
            """

            cursor.execute(multi_query, params + characters)
            multi_chars = [row[0] for row in cursor.fetchall()]

            final_results.append((query_info['path_string'], characters, multi_chars))

    return final_results


def query_by_status(char_list, locations, features, user_input, db_path=DIALECTS_DB_USER, table="dialects"):
    """
    📌 根據提供的漢字名單，查詢其在不同地點與語音特徵（如聲母/韻母）下的分佈情況。

    性能优化：使用SQL GROUP BY代替pandas处理（3-5倍性能提升）

    功能包含：
    - 從 dialects.db 中找出指定地點與漢字的資料
    - 計算每種語音特徵值（如 b, p, m...）的字數、比例（去重後）
    - 處理「多音字」的詳細音節資訊（保留所有對應的發音）
    - 輸出欄位包含：分組值（特徵=值）

    回傳：
    - 每筆統計結果以字典方式輸出，最終轉為 DataFrame
    """
    if not char_list or not locations or not features:
        return pd.DataFrame()
    allowed_features = {"聲母", "韻母", "聲調"}
    features = [f for f in features if f in allowed_features]
    if not features:
        return pd.DataFrame()

    pool = get_db_pool(db_path)
    results = []

    with pool.get_connection() as conn:
        cursor = conn.cursor()

        # 【SQL优化】一次性查询所有数据
        loc_placeholders = ','.join(['?'] * len(locations))
        char_placeholders = ','.join(['?'] * len(char_list))
        
        query = f"""
        SELECT 簡稱, 漢字, {', '.join(features)}, 多音字, 音節
        FROM {table}
        WHERE 簡稱 IN ({loc_placeholders})
        AND 漢字 IN ({char_placeholders})
        """
        cursor.execute(query, locations + char_list)
        all_rows = cursor.fetchall()

        print(f"[OK] 查詢結果：載入 {len(all_rows)} 條資料")

        # 构建列索引
        col_indices = {'簡稱': 0, '漢字': 1, '多音字': len(features) + 2, '音節': len(features) + 3}
        for i, feat in enumerate(features):
            col_indices[feat] = i + 2

        # 【SQL优化】查询多音字（使用SQL GROUP BY）
        poly_query = f"""
        SELECT 簡稱, 漢字, GROUP_CONCAT(音節, '|') as prons
        FROM {table}
        WHERE 多音字 = '1'
        AND 簡稱 IN ({loc_placeholders})
        AND 漢字 IN ({char_placeholders})
        GROUP BY 簡稱, 漢字
        """
        cursor.execute(poly_query, locations + char_list)
        poly_rows = cursor.fetchall()

        # 构建多音字字典 {(loc, hz): prons}
        poly_dict = {(row[0], row[1]): row[2] for row in poly_rows}

    # 使用Python字典进行分组（代替pandas groupby）
    from collections import defaultdict
    
    # 按地点分组数据
    loc_data = defaultdict(list)
    for row in all_rows:
        loc = row[col_indices['簡稱']]
        loc_data[loc].append(row)

    # 处理每个地点
    for loc in locations:
        rows = loc_data.get(loc, [])
        
        if not rows:
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

        # 计算该地点的总字数
        total_chars = len(set(row[col_indices['漢字']] for row in rows))

        # 处理每个特征
        for feature in features:
            feature_idx = col_indices[feature]
            
            # 按特征值分组
            feature_groups = defaultdict(set)  # {feature_value: set(chars)}
            for row in rows:
                fval = row[feature_idx]
                if fval:  # 跳过NULL
                    hz = row[col_indices['漢字']]
                    feature_groups[fval].add(hz)

            # 生成结果
            for fval, chars_set in feature_groups.items():
                unique_chars = list(chars_set)
                count = len(unique_chars)

                # 构建多音字详情
                poly_details = []
                for hz in unique_chars:
                    prons = poly_dict.get((loc, hz))
                    if prons:
                        poly_details.append(f"{hz}:{prons}")

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
    match_results = match_locations_batch_exact(" ".join(locations_new))
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


def query_by_status_stats_only(char_list, locations, features, db_path=DIALECTS_DB_USER, table="dialects"):
    """
    Compare API stats-only fast path.
    Returns nested structure by location -> feature with values/total.

    Performance optimization:
    - Uses optimal index (簡稱, 漢字) to fetch all matching rows
    - Performs aggregation in Python instead of SQL
    - 10x faster than using (簡稱, feature) indexes
    """
    if not char_list or not locations or not features:
        return {}
    allowed_features = {"\u8072\u6bcd", "\u97fb\u6bcd", "\u8072\u8abf"}
    features = [f for f in features if f in allowed_features]
    if not features:
        return {}

    pool = get_db_pool(db_path)
    locations = list(dict.fromkeys(locations))
    features = list(dict.fromkeys(features))
    results = {
        loc: {feature: {"values": [], "total": 0} for feature in features}
        for loc in locations
    }

    with pool.get_connection() as conn:
        # Fetch all data using optimal index (簡稱, 漢字)
        loc_placeholders = ','.join('?' for _ in locations)
        char_placeholders = ','.join('?' for _ in char_list)

        # Build dynamic column list for features
        feature_cols = ', '.join(features)
        query = f"""
        SELECT \u7c21\u7a31, \u6f22\u5b57, {feature_cols}
        FROM {table}
        WHERE \u7c21\u7a31 IN ({loc_placeholders})
        AND \u6f22\u5b57 IN ({char_placeholders})
        """
        params = locations + char_list
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()

    # Aggregate in Python (faster than SQL GROUP BY + COUNT(DISTINCT))
    from collections import defaultdict

    # Build stats: {loc: {feature: {value: set(chars)}}}
    stats = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))

    for row in rows:
        loc = row[0]
        char = row[1]
        for i, feature in enumerate(features):
            value = row[2 + i]  # Feature values start at index 2
            if value:  # Skip NULL and empty strings
                stats[loc][feature][value].add(char)

    # Convert to output format
    for loc in locations:
        for feature in features:
            feature_stats = stats.get(loc, {}).get(feature, {})
            total = sum(len(chars) for chars in feature_stats.values())
            values = [
                {
                    "value": value,
                    "count": len(chars),
                    "percentage": round(len(chars) / total * 100, 2) if total > 0 else 0
                }
                for value, chars in sorted(feature_stats.items(), key=lambda x: len(x[1]), reverse=True)
            ]
            results[loc][feature] = {
                "values": values,
                "total": total
            }

    return results

