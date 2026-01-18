import itertools

from app.redis_client import redis_client
from app.service.match_input_tip import match_locations_batch
from app.service.status_arrange_pho import query_characters_by_path, query_by_status, convert_path_str
from common.config import DIALECTS_DB_USER
from common.constants import COLUMN_VALUES

import json
import hashlib
import time
import asyncio
from typing import List, Dict, Optional, Any
import redis.asyncio as redis

from common.getloc_by_name_region import query_dialect_abbreviations


def process_chars_status(path_strings, column, combine_query):
    """
    处理 path_strings 和 column 的组合查询逻辑
    """
    result = []

    # 如果 path_strings 是单个字符串，则转换为列表（为了兼容多种用法）
    if isinstance(path_strings, str):
        path_strings = [path_strings]

    if path_strings:
        for path_string in path_strings:
            if combine_query:
                # 如果 combine_query 为 True, 处理 path_string 和 column 组合叠加
                value_combinations = []
                for col in column:
                    values = COLUMN_VALUES.get(col)
                    if values:
                        value_combinations.append(values)

                # 生成跨列组合，并叠加 path_string 中的查询条件
                if value_combinations:
                    for value_combination in itertools.product(*value_combinations):
                        # 构建新的查询字符串：path_string + 每一列的值
                        query_string = path_string
                        for value, col in zip(value_combination, column):
                            query_string += f"[{value}]{{{col}}}"

                        # 查询生成的组合
                        characters, _ = query_characters_by_path(query_string)
                        if characters:
                            display_name = convert_path_str(query_string)
                            result.append({'query': display_name, '字数': len(characters), '汉字': characters})
            else:
                # 如果直接传入了 query_string，則直接查詢並將結果附加到 result 中
                characters, _ = query_characters_by_path(path_string)
                if characters:
                    display_name = convert_path_str(path_string)
                    result.append({'query': display_name, '字数': len(characters), '汉字': characters})

    return result


def _run_dialect_analysis_sync(
        char_data_list: List[Dict],
        locations: List[str],
        regions: List[str],
        features: List[str],
        region_mode: str = 'yindian',
        db_path_dialect: str = DIALECTS_DB_USER
):
    """
    這是 sta2pho 的後半部分邏輯重寫版。
    它不查字，直接用 char_data_list 裡的字去查方言。
    """
    # 1. 處理地點簡稱 (複製原邏輯)
    locations_new = query_dialect_abbreviations(regions, locations, region_mode=region_mode)
    match_results = match_locations_batch(" ".join(locations_new))

    # 檢查匹配結果
    if not any(res[1] == 1 for res in match_results):
        # 這裡可以選擇拋出錯誤或返回空
        return []

    unique_abbrs = list({abbr for res in match_results for abbr in res[0]})

    all_results = []

    # 2. 遍歷緩存查出來的漢字數據
    for item in char_data_list:
        path_str = item.get('query', '未知條件')
        path_chars = item.get('汉字', [])

        if not path_chars:
            continue

        # 3. 針對每個特徵調用底層的 query_by_status
        for feature in features:
            # ✅ 這裡直接調用你原本的底層函數，完全不需要改動它
            df = query_by_status(
                char_list=path_chars,
                locations=unique_abbrs,
                features=[feature],
                user_input=path_str,  # 用查詢條件作為顯示標籤
                db_path=db_path_dialect
            )

            # 將 DataFrame 轉為字典格式以便 JSON 序列化
            if not df.empty:
                all_results.append(df.to_dict(orient="records"))

    return all_results


# --- 1. 生成唯一的 Cache Key ---
def generate_cache_key(path_strings: Any, column: Any, combine_query: bool) -> str:
    """
    生成标准化的缓存 Key
    核心逻辑：暴力清洗数据，将 None 视为 []，确保 Key 的唯一性
    """

    # ==========================================
    # 👇 关键修改：数据清洗 (Normalization)
    # ==========================================
    # 逻辑：如果是 None (没传)，或者 False (空列表)，统一变成 []
    safe_path = path_strings if path_strings else []
    safe_col = column if column else []

    # 可选：如果你希望 ["A", "B"] 和 ["B", "A"] 视为同一个缓存，可以排序
    # safe_path.sort()
    # safe_col.sort()

    # 构建用于生成 Hash 的字典
    key_data = {
        "path": safe_path,
        "col": safe_col,
        "combine": bool(combine_query)  # 强转 bool，防止 0/1 差异
    }

    # 序列化为字符串
    # sort_keys=True 保证字典顺序一致
    # ensure_ascii=False 保证中文字符一致
    key_str = json.dumps(key_data, sort_keys=True, ensure_ascii=False)

    # 生成 MD5
    return "charlist:" + hashlib.md5(key_str.encode('utf-8')).hexdigest()

# 緩存讀取 (Async)
async def get_cache(key: str) -> Optional[List[Dict]]:
    try:
        # ✅ 加上 await
        cached_val = await redis_client.get(key)
        if cached_val:
            print(f"🔥 [Redis Cache] Hit: {key}")
            return json.loads(cached_val)
    except Exception as e:
        print(f"❌ Redis Read Error: {e}")
    return None

# 緩存寫入 (Async)
async def set_cache(key: str, data: List[Dict], expire_seconds: int = 600):
    try:
        # ✅ 加上 await
        await redis_client.set(key, json.dumps(data), ex=expire_seconds)
        print(f"💾 [Redis Cache] Set: {key}")
    except Exception as e:
        print(f"❌ Redis Write Error: {e}")
