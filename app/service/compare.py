"""
[PKG] 服务模块：字音比较功能
[PKG] 服务模块：声调系统比较功能
"""

import numpy as np
from itertools import combinations
from fastapi import HTTPException

from app.common.path import DIALECTS_DB_USER, QUERY_DB_USER
from app.common.s2t import s2t_pro
from app.service.getloc_by_name_region import query_dialect_abbreviations
from app.service.search_tones import search_tones
from app.sql.db_pool import get_db_pool


def compare_characters(
    chars,
    features,
    locations=None,
    regions=None,
    db_path=DIALECTS_DB_USER,
    region_mode='yindian',
    query_db_path=QUERY_DB_USER
):
    """
    比较多个汉字在不同地点的音韵特征差异

    Args:
        chars: 汉字列表（至少2个）
        features: 要比较的特征列表（聲母/韻母/聲調）
        locations: 地点列表
        regions: 分区列表
        db_path: 方言数据库路径
        region_mode: 分区模式
        query_db_path: 查询数据库路径

    Returns:
        按地点分组的比较结果
    """
    # 验证输入
    if len(chars) < 2:
        raise HTTPException(status_code=400, detail="至少需要2个汉字进行比较")

    valid_features = {"聲母", "韻母", "聲調"}
    invalid_features = set(features) - valid_features
    if invalid_features:
        raise HTTPException(
            status_code=400,
            detail=f"无效的特征：{invalid_features}，只支持：聲母/韻母/聲調"
        )

    # 获取地点列表
    all_locations = query_dialect_abbreviations(
        regions, locations, db_path=query_db_path, region_mode=region_mode
    )
    if not all_locations:
        raise HTTPException(
            status_code=400,
            detail="🛑 請輸入正確的地點！\\n建議點擊地點輸入框下方的提示地點！"
        )

    # 标准化输入
    if isinstance(chars, str):
        chars = list(chars)
    elif isinstance(chars, (list, np.ndarray)):
        chars = [char for sublist in chars for char in
                 (sublist if isinstance(sublist, (list, np.ndarray)) else [sublist])]

    # 使用 s2t_pro 进行简繁转换
    clean_str, mapping = s2t_pro(chars, level=2, keep_all_layers=True)

    # 构建每个原字的候选列表
    char2candidates = {}
    for 原字, 候選 in mapping:
        candidates = [原字] + [c for c in 候選 if c != 原字]
        char2candidates[原字] = candidates

    # 收集所有候选字
    all_candidate_chars = []
    for 原字 in chars:
        all_candidate_chars.extend(char2candidates.get(原字, [原字]))
    clean_str = ''.join(dict.fromkeys(all_candidate_chars))

    # 批量查询方言数据
    char2loc2data = {}  # {char: {location: [rows]}}

    dialect_pool = get_db_pool(db_path)
    with dialect_pool.get_connection() as dialect_conn:
        dialect_cursor = dialect_conn.cursor()

        if clean_str and all_locations:
            MAX_PARAMS = 900
            char_loc_pairs = [(c, loc) for c in clean_str for loc in all_locations]

            for i in range(0, len(char_loc_pairs), MAX_PARAMS // 2):
                batch = char_loc_pairs[i:i + MAX_PARAMS // 2]
                pair_placeholders = ','.join(['(?,?)'] * len(batch))
                flat_params = [val for pair in batch for val in pair]

                dialect_query = f"""
                    SELECT 漢字, 簡稱, 聲母, 韻母, 聲調
                    FROM dialects
                    WHERE (漢字, 簡稱) IN ({pair_placeholders})
                """
                dialect_cursor.execute(dialect_query, flat_params)
                batch_results = dialect_cursor.fetchall()

                for row in batch_results:
                    char = row['漢字']
                    loc = row['簡稱']
                    if char not in char2loc2data:
                        char2loc2data[char] = {}
                    if loc not in char2loc2data[char]:
                        char2loc2data[char][loc] = []
                    char2loc2data[char][loc].append(row)

    # 构建比较结果
    results = []

    for location in all_locations:
        comparisons = []

        # 生成所有字对组合
        for char1, char2 in combinations(chars, 2):
            pair_comparison = {
                "pair": [char1, char2],
                "features": {}
            }

            # 获取两个字的所有候选字
            candidates1 = char2candidates.get(char1, [char1])
            candidates2 = char2candidates.get(char2, [char2])

            # 收集两个字在该地点的所有特征值
            char1_features = _collect_features(candidates1, location, char2loc2data)
            char2_features = _collect_features(candidates2, location, char2loc2data)

            # 比较每个特征
            for feature in features:
                values1 = char1_features.get(feature, set())
                values2 = char2_features.get(feature, set())

                comparison_result = _compare_feature_values(
                    char1, char2, values1, values2
                )
                pair_comparison["features"][feature] = comparison_result

            comparisons.append(pair_comparison)

        results.append({
            "location": location,
            "comparisons": comparisons
        })

    return results


def _collect_features(candidates, location, char2loc2data):
    """
    收集候选字在指定地点的所有特征值

    Returns:
        {
            "聲母": {"g", "k"},
            "韻母": {"aau"},
            "聲調": {"1", "2"}
        }
    """
    features = {
        "聲母": set(),
        "韻母": set(),
        "聲調": set()
    }

    for candidate in candidates:
        rows = char2loc2data.get(candidate, {}).get(location, [])
        for row in rows:
            row_dict = dict(row)
            if row_dict.get('聲母'):
                features["聲母"].add(row_dict['聲母'])
            if row_dict.get('韻母'):
                features["韻母"].add(row_dict['韻母'])
            if row_dict.get('聲調'):
                features["聲調"].add(str(row_dict['聲調']))

    return features


def _compare_feature_values(char1, char2, values1, values2):
    """
    比较两个字的特征值集合

    Returns:
        {
            "status": "same" | "diff" | "partial" | "unknown",
            "value": "..." (when same),
            "values": {"char1": [...], "char2": [...]} (when diff/partial/unknown)
        }
    """
    # 移除空值
    values1 = {v for v in values1 if v}
    values2 = {v for v in values2 if v}

    # 检查是否包含"未知"（声调特有的情况）
    has_unknown_1 = "未知" in values1
    has_unknown_2 = "未知" in values2

    # 如果有一方包含"未知"，返回 unknown
    if has_unknown_1 or has_unknown_2:
        return {
            "status": "unknown",
            "values": {
                char1: sorted(list(values1)),
                char2: sorted(list(values2))
            }
        }

    # 如果有一方为空（声母/韵母的情况），返回 unknown
    if not values1 or not values2:
        return {
            "status": "unknown",
            "values": {
                char1: sorted(list(values1)) if values1 else [],
                char2: sorted(list(values2)) if values2 else []
            }
        }

    # 计算交集
    intersection = values1 & values2

    if values1 == values2:
        # 完全相同
        return {
            "status": "same",
            "value": sorted(list(values1))[0] if len(values1) == 1 else ", ".join(sorted(list(values1)))
        }
    elif not intersection:
        # 完全不同
        return {
            "status": "diff",
            "values": {
                char1: sorted(list(values1)),
                char2: sorted(list(values2))
            }
        }
    else:
        # 部分相同
        return {
            "status": "partial",
            "values": {
                char1: sorted(list(values1)),
                char2: sorted(list(values2))
            }
        }


def compare_tones(
    tone_classes,
    locations=None,
    regions=None,
    db_path=QUERY_DB_USER,
    region_mode='yindian'
):
    """
    比较同一地点内不同调类的合并关系

    Args:
        tone_classes: 要比较的调类编号列表，如 [1, 2, 3] 表示 T1, T2, T3
        locations: 地点列表
        regions: 分区列表
        db_path: 查询数据库路径
        region_mode: 分区模式

    Returns:
        按地点分组的调类比较结果
    """
    # 验证输入
    if len(tone_classes) < 2:
        raise HTTPException(status_code=400, detail="至少需要2个调类进行比较")

    # 验证调类编号范围
    for tc in tone_classes:
        if not isinstance(tc, int) or tc < 1 or tc > 10:
            raise HTTPException(
                status_code=400,
                detail=f"无效的调类编号：{tc}，必须是 1-10 之间的整数"
            )

    # 获取声调数据（使用 get_raw=True 获取完整数据，包括 match 字段）
    tones_data = search_tones(
        locations=locations,
        regions=regions,
        get_raw=True,  # 获取完整数据结构
        db_path=db_path,
        region_mode=region_mode
    )

    if not tones_data:
        raise HTTPException(
            status_code=400,
            detail="🛑 請輸入正確的地點！\\n建議點擊地點輸入框下方的提示地點！"
        )

    # 构建比较结果
    results = []

    for location_data in tones_data:
        location = location_data['簡稱']

        comparisons = []

        # 生成所有调类对的组合
        from itertools import combinations
        for tc1, tc2 in combinations(tone_classes, 2):
            t1_key = f"T{tc1}"
            t2_key = f"T{tc2}"

            # 获取调类数据
            t1_data = location_data.get(t1_key, {})
            t2_data = location_data.get(t2_key, {})

            # 比较两个调类
            comparison_result = _compare_tone_classes(
                t1_key, t2_key, t1_data, t2_data
            )

            comparisons.append({
                "pair": [t1_key, t2_key],
                "comparison": comparison_result
            })

        results.append({
            "location": location,
            "comparisons": comparisons
        })

    return results


def _compare_tone_classes(t1_key, t2_key, t1_data, t2_data):
    """
    比较两个调类的合并关系

    Args:
        t1_key: 第一个调类键（如 "T1"）
        t2_key: 第二个调类键（如 "T3"）
        t1_data: 第一个调类的完整数据（包含 value, name, match 等字段）
        t2_data: 第二个调类的完整数据

    Returns:
        {
            "status": "same" | "partial" | "diff" | "unknown",
            "t1_value": list,  # 调值列表
            "t2_value": list,
            "t1_match": list,  # match 列表
            "t2_match": list,
            "intersection": dict  # 当 status=partial 时的交集 {"match": [...], "value": [...]}
        }
    """
    # 获取 value 和 match
    t1_value = t1_data.get('value', [])
    t2_value = t2_data.get('value', [])
    t1_match = t1_data.get('match', [])
    t2_match = t2_data.get('match', [])

    # 处理 match 字段可能是字符串的情况（如 "T5" 或 "T3,T5"）
    if isinstance(t1_match, str):
        if t1_match == '無' or not t1_match:
            t1_match = []
        else:
            t1_match = [m.strip() for m in t1_match.split(',')]

    if isinstance(t2_match, str):
        if t2_match == '無' or not t2_match:
            t2_match = []
        else:
            t2_match = [m.strip() for m in t2_match.split(',')]

    # 获取 name 字段（用于 maybe 判断）
    t1_name = t1_data.get('name', [])
    t2_name = t2_data.get('name', [])

    # 转换为集合进行比较
    t1_match_set = set(t1_match) if t1_match else set()
    t2_match_set = set(t2_match) if t2_match else set()
    t1_value_set = set(t1_value) if t1_value else set()
    t2_value_set = set(t2_value) if t2_value else set()

    # 计算交集
    match_intersection = t1_match_set & t2_match_set
    value_intersection = t1_value_set & t2_value_set

    # 情况1：same - match 完全相同（优先判断 match）
    if t1_match_set and t2_match_set and t1_match_set == t2_match_set:
        return {
            "status": "same",
            "t1_value": t1_value,
            "t2_value": t2_value,
            "t1_match": t1_match,
            "t2_match": t2_match
        }

    # 情况1a：互相引用判断 - 如果 T1 的 match 包含 T2，且 T2 的 match 包含 T1
    if t1_match_set and t2_match_set:
        if t2_key in t1_match_set and t1_key in t2_match_set:
            return {
                "status": "same",
                "t1_value": t1_value,
                "t2_value": t2_value,
                "t1_match": t1_match,
                "t2_match": t2_match
            }

    # 情况1b：如果 match 都为空，则比较 value
    if not t1_match_set and not t2_match_set and t1_value_set == t2_value_set:
        return {
            "status": "same",
            "t1_value": t1_value,
            "t2_value": t2_value,
            "t1_match": t1_match,
            "t2_match": t2_match
        }

    # 情况2：partial - match 有交集 OR value 有交集
    if match_intersection or value_intersection:
        intersection_result = {}
        if match_intersection:
            intersection_result["match"] = sorted(list(match_intersection))
        if value_intersection:
            intersection_result["value"] = sorted(list(value_intersection))

        return {
            "status": "partial",
            "t1_value": t1_value,
            "t2_value": t2_value,
            "t1_match": t1_match,
            "t2_match": t2_match,
            "intersection": intersection_result
        }

    # 情况3：diff - match 和 value 都没有交集
    result = {
        "status": "diff",
        "t1_value": t1_value,
        "t2_value": t2_value,
        "t1_match": t1_match,
        "t2_match": t2_match,
        "t1_name": t1_name,
        "t2_name": t2_name
    }

    # 在返回 diff 之前，检查是否满足 maybe 条件
    # 规则1：T6 vs T5 - 如果 T6 为空但 T5 的 name 完全匹配"去"相关
    if t1_key == "T6" and t2_key == "T5":
        if not t1_value and not t1_match:
            # 检查 T5 的 name 是否完全匹配"去"相关
            if any(name in ["去", "去聲", "去声"] for name in t2_name):
                return {
                    "status": "maybe",
                    "t1_value": t1_value,
                    "t2_value": t2_value,
                    "t1_match": t1_match,
                    "t2_match": t2_match,
                    "t1_name": t1_name,
                    "t2_name": t2_name,
                    "reason": "T6为空，T5为去声"
                }
    elif t1_key == "T5" and t2_key == "T6":
        if not t2_value and not t2_match:
            # 检查 T5 的 name 是否完全匹配"去"相关
            if any(name in ["去", "去聲", "去声"] for name in t1_name):
                return {
                    "status": "maybe",
                    "t1_value": t1_value,
                    "t2_value": t2_value,
                    "t1_match": t1_match,
                    "t2_match": t2_match,
                    "t1_name": t1_name,
                    "t2_name": t2_name,
                    "reason": "T6为空，T5为去声"
                }

    # 规则2：T8 vs T7 - 如果 T8 为空但 T7 的 name 完全匹配"入"相关
    if t1_key == "T8" and t2_key == "T7":
        if not t1_value and not t1_match:
            # 检查 T7 的 name 是否完全匹配"入"相关
            if any(name in ["入", "入聲", "入声", "仄"] for name in t2_name):
                return {
                    "status": "maybe",
                    "t1_value": t1_value,
                    "t2_value": t2_value,
                    "t1_match": t1_match,
                    "t2_match": t2_match,
                    "t1_name": t1_name,
                    "t2_name": t2_name,
                    "reason": "T8为空，T7为入声"
                }
    elif t1_key == "T7" and t2_key == "T8":
        if not t2_value and not t2_match:
            # 检查 T7 的 name 是否完全匹配"入"相关
            if any(name in ["入", "入聲", "入声", "仄"] for name in t1_name):
                return {
                    "status": "maybe",
                    "t1_value": t1_value,
                    "t2_value": t2_value,
                    "t1_match": t1_match,
                    "t2_match": t2_match,
                    "t1_name": t1_name,
                    "t2_name": t2_name,
                    "reason": "T8为空，T7为入声"
                }

    # 最后检查 unknown：如果有一方或两方为空（且不满足 maybe 条件）
    if (not t1_value and not t1_match) or (not t2_value and not t2_match):
        return {
            "status": "unknown",
            "t1_value": t1_value,
            "t2_value": t2_value,
            "t1_match": t1_match,
            "t2_match": t2_match,
            "t1_name": t1_name,
            "t2_name": t2_name
        }

    # 返回 diff
    return result
