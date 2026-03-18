import os
import re
import threading
from collections import defaultdict
from typing import Optional

from opencc import OpenCC
from pypinyin import lazy_pinyin
from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from app.service.auth.database.models import User
from app.service.user.core.models import Information
from app.service.geo.getloc_by_name_region import query_dialect_abbreviations_orm
from app.common.path import QUERY_DB_ADMIN
from app.common.s2t import s2t_pro
# [NEW] 导入连接池
from app.sql.db_pool import get_db_pool

# ===== [NEW] 内存缓存机制 =====
# 缓存锁，用于线程安全
_cache_lock = threading.Lock()

# 缓存数据结构
_dialect_cache = {
    'valid_abbrs': {},      # {db_path: {filter_flag: set()}}
    'geo_data': {},         # {db_path: {filter_flag: [(name, abbr), ...]}}
    'geo_pinyin': {},       # {db_path: {filter_flag: {name: pinyin_str}}}
    'last_update': {}       # {db_path: timestamp}
}


def _load_dialect_cache(query_db, filter_valid_abbrs_only):
    """
    加载方言数据到内存缓存

    Args:
        query_db: 数据库路径
        filter_valid_abbrs_only: 是否只加载存储标记为1的数据

    Returns:
        (valid_abbrs_set, geo_data_list, geo_pinyin_map)
    """
    cache_key = (query_db, filter_valid_abbrs_only)

    # 检查缓存是否存在
    with _cache_lock:
        if query_db in _dialect_cache['valid_abbrs']:
            if filter_valid_abbrs_only in _dialect_cache['valid_abbrs'][query_db]:
                # 缓存命中
                valid_abbrs = _dialect_cache['valid_abbrs'][query_db][filter_valid_abbrs_only]
                geo_data = _dialect_cache['geo_data'][query_db][filter_valid_abbrs_only]
                geo_pinyin = _dialect_cache['geo_pinyin'][query_db][filter_valid_abbrs_only]
                return valid_abbrs, geo_data, geo_pinyin

    # 缓存未命中，从数据库加载
    pool = get_db_pool(query_db)
    with pool.get_connection() as conn:
        cursor = conn.cursor()

        # 加载有效简称
        if filter_valid_abbrs_only:
            cursor.execute("SELECT 簡稱 FROM dialects WHERE 存儲標記 = 1")
        else:
            cursor.execute("SELECT 簡稱 FROM dialects")
        valid_abbrs_set = set(row[0] for row in cursor.fetchall())

        # 加载所有地理名称数据
        geo_data_list = []
        for col in ["市", "縣", "鎮", "行政村", "自然村"]:
            if filter_valid_abbrs_only:
                cursor.execute(f"SELECT {col}, 簡稱 FROM dialects WHERE 存儲標記 = 1")
            else:
                cursor.execute(f"SELECT {col}, 簡稱 FROM dialects")
            rows = cursor.fetchall()
            geo_data_list.extend(rows)

    # 预计算拼音
    geo_pinyin_map = {}
    geo_names_seen = set()
    for name, abbr in geo_data_list:
        if name and name not in geo_names_seen:
            geo_names_seen.add(name)
            geo_pinyin_map[name] = ''.join(lazy_pinyin(name)).lower()

    # 存入缓存
    with _cache_lock:
        if query_db not in _dialect_cache['valid_abbrs']:
            _dialect_cache['valid_abbrs'][query_db] = {}
            _dialect_cache['geo_data'][query_db] = {}
            _dialect_cache['geo_pinyin'][query_db] = {}

        _dialect_cache['valid_abbrs'][query_db][filter_valid_abbrs_only] = valid_abbrs_set
        _dialect_cache['geo_data'][query_db][filter_valid_abbrs_only] = geo_data_list
        _dialect_cache['geo_pinyin'][query_db][filter_valid_abbrs_only] = geo_pinyin_map
        _dialect_cache['last_update'][query_db] = __import__('time').time()

    print(f"[CACHE] 已加载方言数据到缓存: {len(valid_abbrs_set)} 个简称, {len(geo_data_list)} 条地理数据, {len(geo_pinyin_map)} 个拼音")

    return valid_abbrs_set, geo_data_list, geo_pinyin_map


def clear_dialect_cache(query_db=None):
    """
    清除方言数据缓存

    Args:
        query_db: 指定数据库路径，如果为None则清除所有缓存
    """
    with _cache_lock:
        if query_db:
            _dialect_cache['valid_abbrs'].pop(query_db, None)
            _dialect_cache['geo_data'].pop(query_db, None)
            _dialect_cache['geo_pinyin'].pop(query_db, None)
            _dialect_cache['last_update'].pop(query_db, None)
            print(f"[CACHE] 已清除缓存: {query_db}")
        else:
            _dialect_cache['valid_abbrs'].clear()
            _dialect_cache['geo_data'].clear()
            _dialect_cache['geo_pinyin'].clear()
            _dialect_cache['last_update'].clear()
            print("[CACHE] 已清除所有缓存")


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

    # [NEW] 使用连接池
    pool = get_db_pool(db_path)
    with pool.get_connection() as conn:
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
                          "hasChildren": bool(result[region])  # [OK] 判斷是否有子分區
        }

    return result


def match_custom_feature(locations, regions, keyword, user: Optional[User], db: Session):
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

    # ✅ 处理匿名用户情况
    if user is None:
        # 匿名用户：返回空结果
        return result

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
                    "聲韻調": record.聲韻調,
                    "特徵": 特徵
                })
                continue

            # 拼音模糊比對
            特徵_pinyin = ''.join(lazy_pinyin(特徵))
            ratio = fuzz.ratio(word_pinyin, 特徵_pinyin) / 100.0
            if ratio > 0.7:
                result.append({
                    "簡稱": record.簡稱,
                    "聲韻調": record.聲韻調,
                    "特徵": 特徵
                })

    return result


def match_locations_exact(user_input, filter_valid_abbrs_only=True, query_db=QUERY_DB_ADMIN):
    """
    精确匹配地点简称（快速路径，用于ZhongGu/YinWei）

    只做精确匹配，不做模糊匹配、拼音匹配、相似度计算等。

    Args:
        user_input: 用户输入的地点名称
        filter_valid_abbrs_only: 是否只匹配有存储标记的简称
        query_db: 查询数据库路径

    Returns:
        (matched_abbrs, success_flag)
        - matched_abbrs: list[str] - 匹配到的简称列表
        - success_flag: int - 1表示找到精确匹配，0表示未找到
    """
    user_input = user_input.strip()
    if not user_input:
        return [], 0

    # 1. 简繁转换（复用现有逻辑）
    converted_str, mapping = s2t_pro(user_input, level=2)
    input_len = len(user_input)

    # 生成严格候选集（不交叉混用）
    def generate_strict_candidates(mapping, input_len):
        combinations = [[]]
        for _, candidates in mapping:
            new_combos = []
            for combo in combinations:
                for c in candidates:
                    new_combos.append(combo + [c])
            combinations = new_combos
        return {''.join(chars) for chars in combinations if len(chars) == input_len}

    converted_candidates = generate_strict_candidates(mapping, input_len)

    # possible_inputs 包含：原输入 + 转换字词 + 候选组合
    possible_inputs = {user_input, converted_str} | converted_candidates

    # 2. 加载缓存（复用现有缓存机制）
    valid_abbrs_set, _, _ = _load_dialect_cache(query_db, filter_valid_abbrs_only)

    # 3. 精确匹配
    matched_abbrs = set()
    for term in possible_inputs:
        if term in valid_abbrs_set:
            matched_abbrs.add(term)

    # 4. 返回结果
    if matched_abbrs:
        return list(matched_abbrs), 1
    else:
        return [], 0


def match_locations_batch_exact(input_string: str, filter_valid_abbrs_only=True, query_db=QUERY_DB_ADMIN):
    """
    批量精确匹配地点简称（快速路径）

    Args:
        input_string: 用空格/逗号等分隔的地点字符串
        filter_valid_abbrs_only: 是否只匹配有存储标记的简称
        query_db: 查询数据库路径

    Returns:
        list of (matched_abbrs, success_flag, [], [], [], [], [], []) tuples
        返回格式与 match_locations_batch 兼容，但后6个元素为空列表
    """
    input_string = input_string.strip()
    if not input_string:
        return []

    # 以多种分隔符切分
    parts = re.split(r"[ ,;/，；、]+", input_string)
    results = []

    for part in parts:
        part = part.strip()
        if part:
            try:
                matched_abbrs, success_flag = match_locations_exact(
                    part, filter_valid_abbrs_only, query_db
                )
                # 转换为与原match_locations_batch相同的返回格式
                # (abbrs, success, geo_matches, geo_abbrs, fuzzy_geo, fuzzy_abbrs, sound_like, sound_abbrs)
                results.append((matched_abbrs, success_flag, [], [], [], [], [], []))
            except Exception as e:
                print(f"[X] 精确匹配发生错误：{e}")
                results.append(([], 0, [], [], [], [], [], []))

    return results


def match_locations(user_input, filter_valid_abbrs_only=True, exact_only=True, query_db=QUERY_DB_ADMIN):
    def is_pinyin_similar_cached(a, b, threshold, geo_pinyin_map):
        """使用预计算的拼音缓存进行拼音相似度匹配"""
        if not a or not b:
            return False

        # a 是用户输入，需要计算拼音
        a_pinyin = ''.join(lazy_pinyin(a)).lower()

        # b 是地名，使用预计算的拼音
        b_pinyin = geo_pinyin_map.get(b)
        if not b_pinyin:
            b_pinyin = ''.join(lazy_pinyin(b)).lower()

        ratio = fuzz.ratio(a_pinyin, b_pinyin) / 100.0
        return ratio >= threshold

    def is_similar(a, b, threshold=0.7):
        """使用 rapidfuzz 进行字符串相似度匹配"""
        if not a or not b:
            return False
        similarity = fuzz.ratio(a, b) / 100.0
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

    # [OPTIMIZED] 使用缓存数据而不是每次查询数据库
    valid_abbrs_set, geo_data_list, geo_pinyin_map = _load_dialect_cache(query_db, filter_valid_abbrs_only)

    # [OPTIMIZED] 使用内存匹配，完全避免数据库查询
    matched_abbrs = set()
    for term in possible_inputs:
        # 精确匹配：直接在缓存集合中查找
        if term in valid_abbrs_set:
            matched_abbrs.add(term)

    # 如果指定只做完全匹配，但找不到，提前返回空
    if exact_only and not matched_abbrs:
        return [], 0, [], [], [], [], [], []

    # 记录是否找到精确匹配（用于返回值的 success 标志）
    exact_match_found = bool(matched_abbrs)
    # 继续执行后续的模糊匹配逻辑...

    # [OPTIMIZED] 前缀匹配和包含匹配：在内存中遍历
    fuzzy_abbrs = set()
    contains_abbrs = set()

    for term in possible_inputs:
        for abbr in valid_abbrs_set:
            # 前缀匹配
            if abbr.startswith(term):
                fuzzy_abbrs.add(abbr)
            # 包含匹配
            elif term in abbr:
                contains_abbrs.add(abbr)

    # [OPTIMIZED] 使用缓存的地理数据进行匹配
    geo_matches = set()
    geo_abbr_map = {}
    geo_names_set = set()  # 使用 set 去重

    # 去重 + 长度过滤 + 子串匹配
    for name, abbr in geo_data_list:
        if not name or not abbr:
            continue

        # 长度过滤：跳过单字（"市"、"县"、"镇"、"村"等无意义单字）
        if len(name) <= 1:
            continue

        # 去重
        if name not in geo_names_set:
            geo_names_set.add(name)
            geo_abbr_map[name] = abbr

        # 子串匹配
        for term in possible_inputs:
            if term in name:
                geo_matches.add(name)

    all_geo_names = list(geo_names_set)

    # 早期终止检查：如果已有足够结果，跳过昂贵的相似度匹配
    EARLY_TERMINATION_THRESHOLD = 30
    combined_count = len(matched_abbrs) + len(fuzzy_abbrs) + len(contains_abbrs) + len(geo_matches)

    if combined_count >= EARLY_TERMINATION_THRESHOLD:
        # 跳过相似度匹配，构建按优先级排序的结果列表
        result_list = []
        result_list.extend(list(matched_abbrs))
        result_list.extend([a for a in fuzzy_abbrs if a not in matched_abbrs])
        result_list.extend([a for a in contains_abbrs if a not in matched_abbrs and a not in fuzzy_abbrs])

        return (
            result_list,
            1 if exact_match_found else 0,
            list(geo_matches),
            [geo_abbr_map[n] for n in geo_matches if n in geo_abbr_map and geo_abbr_map[n] in valid_abbrs_set],
            [],  # 跳过 fuzzy_geo_matches
            [],  # 跳过 fuzzy_geo_abbrs
            [],  # 跳过 sound_like_matches
            [],  # 跳过 sound_like_abbrs
        )

    # 预筛选相似度候选：按长度和首字符过滤
    user_len = len(user_input)
    user_first = user_input[0] if user_input else ""

    similarity_candidates = []
    for name in all_geo_names:
        # 预筛选规则：长度相近或首字符相同
        if abs(len(name) - user_len) <= 3:  # 长度差距不超过3
            similarity_candidates.append(name)
        elif name.startswith(user_first):  # 或首字符相同
            similarity_candidates.append(name)

    # 限制候选数量
    MAX_SIMILARITY_CANDIDATES = 1000
    if len(similarity_candidates) > MAX_SIMILARITY_CANDIDATES:
        # 优先保留长度最接近的候选
        similarity_candidates.sort(key=lambda x: abs(len(x) - user_len))
        similarity_candidates = similarity_candidates[:MAX_SIMILARITY_CANDIDATES]

    # 加上所有簡稱（用於相似與拼音匹配）
    all_names = similarity_candidates + list(valid_abbrs_set)
    all_abbrs = [geo_abbr_map.get(n, n) for n in similarity_candidates] + list(valid_abbrs_set)

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

        if is_pinyin_similar_cached(user_input, name, 0.9, geo_pinyin_map):
            # print(f"[DEBUG] 拼音匹配: '{user_input}' ≈ '{name}' (abbr: {abbr})")
            sound_like_matches.add(name)
            sound_like_abbrs.add(abbr)

    # 构建按优先级排序的结果列表
    result_list = []
    # 优先级 1：精确匹配
    result_list.extend(list(matched_abbrs))
    # 优先级 2：前缀匹配（去重）
    result_list.extend([a for a in fuzzy_abbrs if a not in matched_abbrs])
    # 优先级 3：包含匹配（去重）
    result_list.extend([a for a in contains_abbrs if a not in matched_abbrs and a not in fuzzy_abbrs])

    return (
        result_list,  # 按优先级排序的合并结果
        1 if exact_match_found else 0,  # 根据是否有精确匹配设置成功标志
        list(geo_matches),
        [geo_abbr_map[n] for n in geo_matches if n in geo_abbr_map and geo_abbr_map[n] in valid_abbrs_set],
        list(fuzzy_geo_matches),
        list(fuzzy_geo_abbrs),
        list(sound_like_matches),
        list(sound_like_abbrs),
    )


def match_locations_batch(input_string: str, filter_valid_abbrs_only=True, exact_only=True, query_db=QUERY_DB_ADMIN
                          , db: Session = None, user=None):
    input_string = input_string.strip()
    if not input_string:
        # print("[!] 輸入為空，無法處理。")
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
                print(f"   [X] 發生錯誤：{e}")
                results.append((False, 0, [], [], [], [], [], []))

    return results


def match_locations_batch_all(locations_list, filter_valid_abbrs_only=True, exact_only=True, query_db=QUERY_DB_ADMIN, db: Session = None, user=None):
    """
    [NEW] 批量处理多个地点输入，一次性处理所有地点以提升性能

    Args:
        locations_list: 地点列表
        filter_valid_abbrs_only: 是否只过滤有效的简称
        exact_only: 是否只进行精确匹配
        query_db: 查询数据库路径
        db: 数据库会话（用于 ORM 查询）
        user: 用户对象

    Returns:
        处理后的地点列表
    """
    if not locations_list:
        return []

    # 如果只有一个地点，直接调用原有函数
    if len(locations_list) == 1:
        if exact_only:
            matched = match_locations_batch_exact(locations_list[0], filter_valid_abbrs_only, query_db)
        else:
            matched = match_locations_batch(locations_list[0], filter_valid_abbrs_only, exact_only, query_db, db, user)
        return [res[0][0] for res in matched if res[0]] if matched else []

    # 批量处理多个地点
    all_processed = []

    # 解析所有输入并合并所有需要查询的部分
    all_parts = []
    for location in locations_list:
        location = location.strip()
        if location:
            parts = re.split(r"[ ,;/，；、]+", location)
            all_parts.extend([p.strip() for p in parts if p.strip()])

    # 去重
    unique_parts = list(dict.fromkeys(all_parts))

    # 批量查询（使用连接池）
    pool = get_db_pool(query_db)
    results_map = {}

    with pool.get_connection() as conn:
        cursor = conn.cursor()

        # 批量精确匹配查询（使用 WHERE IN）
        if unique_parts:
            placeholders = ','.join('?' * len(unique_parts))
            if filter_valid_abbrs_only:
                exact_query = f"SELECT 簡稱 FROM dialects WHERE 簡稱 IN ({placeholders}) AND 存儲標記 = 1"
            else:
                exact_query = f"SELECT 簡稱 FROM dialects WHERE 簡稱 IN ({placeholders})"

            cursor.execute(exact_query, unique_parts)
            exact_matches = {row[0] for row in cursor.fetchall()}

            # 将精确匹配的结果存储到结果映射中
            for part in unique_parts:
                if part in exact_matches:
                    results_map[part] = [part]

    # 提取所有匹配的简称
    for location in locations_list:
        location = location.strip()
        if location:
            parts = re.split(r"[ ,;/，；、]+", location)
            for part in parts:
                part = part.strip()
                if part and part in results_map:
                    all_processed.extend(results_map[part])

    return all_processed
