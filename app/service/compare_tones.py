"""
[PKG] 服务模块：声调系统比较功能
"""

from fastapi import HTTPException

from app.common.path import QUERY_DB_USER
from app.service.search_tones import search_tones


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
