import os
import re
import sqlite3
from collections import defaultdict
from difflib import SequenceMatcher

from opencc import OpenCC
from pypinyin import lazy_pinyin
from sqlalchemy.orm import Session

from app.auth.models import User
from app.custom.models import Information
from common.getloc_by_name_region import query_dialect_abbreviations_orm
from common.config import QUERY_DB_ADMIN
from common.s2t import s2t_pro


def read_partition_hierarchy(parent_regions=None, db_path=QUERY_DB_ADMIN):
    """
    傳入 parent_region，返回它下層的分區：
    - 一級 → 回傳其二級列表
    - 二級 → 回傳其三級列表（僅該一級下）
    - 其他 → []
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"資料庫不存在: {db_path}")

    hierarchy = defaultdict(lambda: defaultdict(list))

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 音典分區 FROM dialects")
        rows = cursor.fetchall()

        for (partition_str,) in rows:
            parts = partition_str.strip().split("-")
            if len(parts) == 1:
                if parts[0] not in hierarchy:
                    hierarchy[parts[0]] = {}
            elif len(parts) == 2:
                if parts[1] not in hierarchy[parts[0]]:
                    hierarchy[parts[0]][parts[1]] = []
            elif len(parts) >= 3:
                if parts[2] not in hierarchy[parts[0]][parts[1]]:
                    hierarchy[parts[0]][parts[1]].append(parts[2])

    # print("完整的 hierarchy 結構:")
    # import json
    # print(json.dumps(hierarchy, ensure_ascii=False, indent=4))
    # 處理 parent_regions 輸入
    if isinstance(parent_regions, str):
        parent_regions = [parent_regions]
    elif not parent_regions:
        return dict(hierarchy)  # 無輸入時返回整體結構

    # 對每個 parent_region 查詢其下層及層級
    result = {}
    for region in parent_regions:
        # print(f"處理區域: {region}")  # 顯示當前處理的區域

        if region in hierarchy:
            # print(f"找到一級分區: {region}")
            result[region] = sorted(hierarchy[region].keys())
            level = 1  # 一級的層級為 1
            # print(f"一級分區的下層分區: {sorted(hierarchy[region].keys())}, 層級: {level}")
        else:
            found = False
            # print(f"在一級分區中未找到: {region}，開始查找二級分區")

            for level1, level2_dict in hierarchy.items():
                # print(f"檢查一級分區 {level1} 下的二級分區")
                if region in level2_dict:
                    # print(f"找到二級分區: {region} 在 {level1} 下")
                    result[region] = sorted(hierarchy[level1][region])
                    level = 2  # 二級的層級為 2
                    # print(f"二級分區的下層分區: {sorted(hierarchy[level1][region])}, 層級: {level}")
                    found = True
                    break

            if not found:
                # print(f"未找到二級分區 {region}，開始查找三級分區")
                result[region] = []

                # 確保三級分區返回空列表並設置層級為 3
                for level1, level2_dict in hierarchy.items():
                    # print(f"檢查一級分區 {level1} 下的二級分區")
                    for level2, level3_list in level2_dict.items():
                        if isinstance(level3_list, list):  # 確保該二級分區擁有三級分區
                            if region in level3_list:
                                # print(f"找到三級分區: {region} 在 {level1}-{level2} 下，設置層級為 3")
                                result[region] = []  # 返回空列表
                                level = 3  # 設置層級為 3
                                found = True
                                break
                    if found:
                        break

                if not found:
                    level = 0  # 無法匹配，層級為 0
                    # print(f"未找到三級分區 {region}，層級設置為 0")

        # print(f"最終結果: {region} -> {result[region]}")

        # 保留原來的結構，並加上 level
        result[region] = {"partitions": result[region],
                          "level": level,
                          "hasChildren": bool(result[region])  # ✅ 判斷是否有子分區
        }

    return result


def match_custom_feature(locations, regions, keyword, user: User, db: Session):
    opencc_t2s = OpenCC('t2s')
    # 候選集初始化
    candidate_set = set()
    candidate_set.add(keyword)

    # 繁體 → 簡體
    try:
        simp = opencc_t2s.convert(keyword)
        candidate_set.add(simp)
    except:
        pass

    # 簡體 → 繁體候選（多對一）
    try:
        trad_string, trad_map = s2t_pro(keyword, level=2)
        candidate_set.add(trad_string)
        for _, 候選列表 in trad_map:
            candidate_set.update(候選列表)
    except:
        pass

    # 拼音比對預備
    word_pinyin = ''.join(lazy_pinyin(keyword))

    # 查詢資料庫位置
    all_locations = query_dialect_abbreviations_orm(
        db, user, regions, locations,
    )

    # 创建结果列表
    result = []

    # 使用 ORM 查询
    for location in all_locations:
        records = db.query(Information).filter(
            Information.user_id == user.id,
            Information.簡稱 == location
        ).all()

        for record in records:
            特徵 = record.特徵

            # 直接或轉換字匹配
            if any(c in 特徵 for c in candidate_set):
                result.append({
                    "簡稱": record.簡稱,
                    "特徵": 特徵
                })
                continue

            # 拼音模糊比對
            特徵_pinyin = ''.join(lazy_pinyin(特徵))
            ratio = SequenceMatcher(None, word_pinyin, 特徵_pinyin).ratio()
            if ratio > 0.7:
                result.append({
                    "簡稱": record.簡稱,
                    "特徵": 特徵
                })

    return result


def match_locations(user_input, filter_valid_abbrs_only=True, exact_only=True, query_db=QUERY_DB_ADMIN):
    def is_pinyin_similar(a, b, threshold=0.9):
        if not a or not b:
            return False
        a_pinyin = ''.join(lazy_pinyin(a)).lower()
        b_pinyin = ''.join(lazy_pinyin(b)).lower()
        ratio = SequenceMatcher(None, a_pinyin, b_pinyin).ratio()
        return ratio >= threshold

    def is_similar(a, b, threshold=0.7):
        if not a or not b:
            return False
        similarity = SequenceMatcher(None, a, b).ratio()
        return similarity >= threshold

    # print(f"[DEBUG] 使用者輸入：{user_input}")

    def generate_strict_candidates(mapping, input_len):
        # 每個位置逐字取候選值組合（不產生交叉混用）
        combinations = [[]]
        for _, candidates in mapping:
            new_combos = []
            for combo in combinations:
                for c in candidates:
                    new_combos.append(combo + [c])
            combinations = new_combos
        # 合併成詞，保證長度一致
        return {''.join(chars) for chars in combinations if len(chars) == input_len}

    # 使用 s2t_pro 轉換
    converted_str, mapping = s2t_pro(user_input, level=2)
    input_len = len(user_input)

    # 安全構造詞組候選集
    converted_candidates = generate_strict_candidates(mapping, input_len)

    # possible_inputs 包含：
    # - 原輸入
    # - 轉換字詞（保證不交叉）
    # - clean_str（第一候選組合）
    possible_inputs = set([user_input, converted_str]) | converted_candidates

    conn = sqlite3.connect(query_db)
    cursor = conn.cursor()

    # 根據 filter_valid_abbrs_only 決定是否過濾掉非存儲標記為1的數據

    if filter_valid_abbrs_only:
        # print("過濾！！")
        cursor.execute("SELECT 簡稱 FROM dialects WHERE 存儲標記 = 1")
    else:
        # print("不過濾存儲標記")
        cursor.execute("SELECT 簡稱 FROM dialects")
    valid_abbrs_set = set(row[0] for row in cursor.fetchall())

    matched_abbrs = set()
    for term in possible_inputs:
        # 完全匹配查詢部分需要根據 filter_valid_abbrs_only 來過濾
        if filter_valid_abbrs_only:
            cursor.execute("SELECT 簡稱 FROM dialects WHERE 簡稱 = ? AND 存儲標記 = 1", (term,))
        else:
            cursor.execute("SELECT 簡稱 FROM dialects WHERE 簡稱 = ?", (term,))
        exact = cursor.fetchall()
        matched_abbrs.update([row[0] for row in exact])
        # print(f"[DEBUG] 完全匹配【{term}】：{exact}")

    # 如果指定只做完全匹配，但找不到，提前返回空
    if exact_only and not matched_abbrs:
        return [], 0, [], [], [], [], [], []

    # 原來的邏輯保留：有完全匹配就返回
    if matched_abbrs:
        return list(matched_abbrs), 1, [], [], [], [], [], []

    fuzzy_abbrs = set()
    for term in possible_inputs:
        # 模糊匹配查詢部分需要根據 filter_valid_abbrs_only 來過濾
        if filter_valid_abbrs_only:
            cursor.execute("SELECT 簡稱 FROM dialects WHERE 簡稱 LIKE ? AND 存儲標記 = 1", (term + "%",))
        else:
            cursor.execute("SELECT 簡稱 FROM dialects WHERE 簡稱 LIKE ?", (term + "%",))
        fuzzy = cursor.fetchall()
        fuzzy_abbrs.update([row[0] for row in fuzzy])
        # print(f"[DEBUG] 模糊簡稱匹配【{term}】：{fuzzy}")

    geo_matches = set()
    geo_abbr_map = {}
    all_geo_names = []
    all_abbr_names = []

    for col in ["鎮", "行政村", "自然村"]:
        if filter_valid_abbrs_only:
            cursor.execute(f"SELECT {col}, 簡稱 FROM dialects WHERE 存儲標記 = 1")
        else:
            cursor.execute(f"SELECT {col}, 簡稱 FROM dialects")
        rows = cursor.fetchall()
        for name, abbr in rows:
            all_geo_names.append(name)
            all_abbr_names.append(abbr)
            for term in possible_inputs:
                if term in (name or ""):
                    geo_matches.add(name)
                    geo_abbr_map[name] = abbr

    # 加上所有簡稱（用於相似與拼音匹配）
    all_names = all_geo_names + list(valid_abbrs_set)
    all_abbrs = all_abbr_names + list(valid_abbrs_set)

    fuzzy_geo_matches = set()
    fuzzy_geo_abbrs = set()
    sound_like_matches = set()
    sound_like_abbrs = set()

    for name, abbr in zip(all_names, all_abbrs):
        if not name or not abbr or abbr not in valid_abbrs_set:
            continue

        if is_similar(user_input, name):
            # print(f"[DEBUG] 相似匹配: '{user_input}' ≈ '{name}' (abbr: {abbr})")
            fuzzy_geo_matches.add(name)
            fuzzy_geo_abbrs.add(abbr)

        if is_pinyin_similar(user_input, name):
            # print(f"[DEBUG] 拼音匹配: '{user_input}' ≈ '{name}' (abbr: {abbr})")
            sound_like_matches.add(name)
            sound_like_abbrs.add(abbr)

    return (
        list(fuzzy_abbrs),
        0,
        list(geo_matches),
        [geo_abbr_map[n] for n in geo_matches if geo_abbr_map[n] in valid_abbrs_set],
        list(fuzzy_geo_matches),
        list(fuzzy_geo_abbrs),
        list(sound_like_matches),
        list(sound_like_abbrs),
    )


def match_locations_batch(input_string: str, filter_valid_abbrs_only=True, exact_only=True, query_db=QUERY_DB_ADMIN
                          , db: Session = None, user=None):
    input_string = input_string.strip()
    if not input_string:
        # print("⚠️ 輸入為空，無法處理。")
        return []

    # 以多種分隔符切分
    parts = re.split(r"[ ,;/，；、]+", input_string)
    results = []

    for idx, part in enumerate(parts):
        part = part.strip()
        if part:
            # print(f"\n🔹 處理第 {idx + 1} 個地名：{part}")
            try:
                res = match_locations(part, filter_valid_abbrs_only, exact_only, query_db=query_db)
                if user and not filter_valid_abbrs_only and not exact_only:
                    def calculate_similarity(str1, str2):
                        # 计算两个字符串的最小长度，避免越界
                        min_len = min(len(str1), len(str2))

                        # 计算两个字符串中相同字符的数量
                        common_chars = sum(1 for i in range(min_len) if str1[i] == str2[i])

                        # 计算相似度（相同字符占总长度的比例）
                        similarity = (common_chars / min_len) * 100
                        return similarity
                    abbreviations = db.query(Information.簡稱).filter(Information.user_id == user.id).all()
                    # 濾出相似度大於50%的簡稱
                    valid_abbrs = [
                        abbr[0] for abbr in abbreviations if calculate_similarity(part, abbr[0]) > 50
                    ]
                    res_with_valid_abbrs = (valid_abbrs + list(res[0]), *res[1:])
                    results.append(res_with_valid_abbrs)
                else:
                    results.append(res)
            except Exception as e:
                print(f"   ❌ 發生錯誤：{e}")
                results.append((False, 0, [], [], [], [], [], []))

    return results
