"""
[PKG] 路由模块：字音比较 API
"""

import asyncio
import hashlib
import json

from fastapi import APIRouter, Query, Depends, HTTPException
from typing import List, Optional
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.auth.database import get_db
from app.sql.db_selector import get_dialects_db, get_query_db
from app.auth.dependencies import get_current_user
# from app.logging.dependencies.limiter import ApiLimiter
from app.auth.models import User
from app.service.match_input_tip import match_locations_batch_all
from app.service.compare import compare_characters, compare_tones
from app.schemas.phonology import CompareZhongGuAnalysis
from app.common.path import QUERY_DB_ADMIN, QUERY_DB_USER, DIALECTS_DB_ADMIN, DIALECTS_DB_USER

router = APIRouter()


@router.get("/compare/chars")
async def compare_chars(
    chars: List[str] = Query(..., description="要比较的汉字列表，至少2个"),
    features: List[str] = Query(..., description="要比较的特征列表：聲母/韻母/聲調"),
    locations: Optional[List[str]] = Query(None, description="要查的地点，可多个"),
    regions: Optional[List[str]] = Query(None, description="要查的分区，可多个"),
    region_mode: str = Query("yindian", description="分区模式，可选 'yindian' 或 'map'"),
    db: Session = Depends(get_db),
    dialects_db: str = Depends(get_dialects_db),
    query_db: str = Depends(get_query_db),
    user: Optional[User] = Depends(get_current_user)
):
    """
    比较多个汉字在不同地点的音韵特征差异

    - chars: 要比较的汉字列表（至少2个）
    - features: 要比较的特征列表（聲母/韻母/聲調）
    - locations: 要查的地点，可多个
    - regions: 要查的分区，可多个
    - region_mode: 分区模式，可选 'yindian' 或 'map'

    返回：
    - results: 按地点分组的比较结果
      - location: 地点名称
      - comparisons: 所有字对的比较结果
        - pair: 比较的字对
        - features: 各特征的比较结果
          - status: same/diff/partial/unknown
            - same: 完全相同
            - diff: 完全不同
            - partial: 部分相同（多音字导致）
            - unknown: 无法判断（有一方数据为空）
          - value: 当 status=same 时的共同值
          - values: 当 status=diff/partial/unknown 时各字的值
    """
    try:
        # 数据库路径已通过依赖注入自动选择
        # 处理地点输入（逻辑与 search_chars 完全一致）
        locations_processed = await run_in_threadpool(
            match_locations_batch_all,
            locations or [],
            filter_valid_abbrs_only=True,
            exact_only=True,
            query_db=query_db,
            db=db,
            user=user
        )

        # 执行比较
        result = await run_in_threadpool(
            compare_characters,
            chars=chars,
            features=features,
            locations=locations_processed,
            regions=regions,
            db_path=dialects_db,
            region_mode=region_mode,
            query_db_path=query_db
        )

        return {"results": result}

    finally:
        print("compare_chars")


@router.get("/compare/tones")
async def compare_tones_route(
    tone_classes: List[int] = Query(..., description="要比较的调类编号列表，如 [1,2,3] 表示 T1,T2,T3"),
    locations: Optional[List[str]] = Query(None, description="要查的地点，可多个"),
    regions: Optional[List[str]] = Query(None, description="要查的分区，可多个"),
    region_mode: str = Query("yindian", description="分区模式，可选 'yindian' 或 'map'"),
    db: Session = Depends(get_db),
    query_db: str = Depends(get_query_db),
    user: Optional[User] = Depends(get_current_user)
):
    """
    比较同一地点内不同调类的合并关系

    - tone_classes: 要比较的调类编号列表（1-10），如 [1,2,3]
    - locations: 要查的地点，可多个
    - regions: 要查的分区，可多个
    - region_mode: 分区模式，可选 'yindian' 或 'map'

    返回：
    - results: 按地点分组的调类比较结果
      - location: 地点名称
      - comparisons: 所有调类对的比较结果
        - pair: 比较的调类对（如 ["T1", "T3"]）
        - comparison: 比较结果
          - status: same/partial/diff/maybe/unknown
            - same: 两个调类完全合并（match 完全相同）
            - partial: 部分合并（match 或 value 有交集但不完全相同）
            - diff: 不合并（match 和 value 都没有交集）
            - maybe: 可能合并（特殊规则：T6为空且T5为去声，或T8为空且T7为入声）
            - unknown: 无法判断（两方都为空，或一方为空但不满足maybe条件）
          - t1_value: 第一个调类的 value 列表（调值）
          - t2_value: 第二个调类的 value 列表
          - t1_match: 第一个调类的 match 列表（匹配的调类）
          - t2_match: 第二个调类的 match 列表
          - t1_name: 第一个调类的 name 列表（调类名称）
          - t2_name: 第二个调类的 name 列表
          - intersection: 当 status=partial 时的交集 {"match": [...], "value": [...]}
          - reason: 当 status=maybe 时的原因说明
    """
    try:
        # 数据库路径已通过依赖注入自动选择
        # 处理地点输入（逻辑与 search_tones 完全一致）
        locations_processed = await run_in_threadpool(
            match_locations_batch_all,
            locations or [],
            filter_valid_abbrs_only=True,
            exact_only=True,
            query_db=query_db,
            db=db,
            user=user
        )

        # 执行比较
        result = await run_in_threadpool(
            compare_tones,
            tone_classes=tone_classes,
            locations=locations_processed,
            regions=regions,
            db_path=query_db,
            region_mode=region_mode
        )

        return {"results": result}

    finally:
        print("compare_tones")


@router.post("/compare/ZhongGu")
async def compare_zhonggu(
    payload: CompareZhongGuAnalysis,
    dialects_db: str = Depends(get_dialects_db),
    query_db: str = Depends(get_query_db)
):
    """
    比较两组中古音条件在方言中的读音差异

    性能优化：
    - 使用轻量级统计查询（不处理多音字详情）
    - 只返回值和占比，不返回具体汉字
    - 预计比标准 ZhongGu API 快 3-5 倍
    """
    from app.service.new_pho import process_chars_status, generate_cache_key, get_cache, set_cache
    from app.service.status_arrange_pho import query_by_status_stats_only
    from app.service.getloc_by_name_region import query_dialect_abbreviations

    try:
        async def _resolve_chars(path_strings, column, combine_query, exclude_columns):
            cache_key = generate_cache_key(
                path_strings,
                column,
                combine_query,
                exclude_columns=exclude_columns
            )
            cached_result = await get_cache(cache_key)
            if cached_result is not None:
                return cached_result
            fresh_result = await run_in_threadpool(
                process_chars_status,
                path_strings,
                column,
                combine_query,
                exclude_columns=exclude_columns
            )
            if fresh_result:
                await set_cache(cache_key, fresh_result, expire_seconds=600)
            return fresh_result

        async def _resolve_stats(chars_unique, locations, features):
            stats_payload = {
                "chars": chars_unique,
                "locations": list(dict.fromkeys(locations)),
                "features": list(dict.fromkeys(features)),
                "db_path": dialects_db
            }
            stats_key = "compare_zhonggu_stats:" + hashlib.sha256(
                json.dumps(stats_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest()
            cached_stats = await get_cache(stats_key)
            if isinstance(cached_stats, dict):
                return cached_stats

            fresh_stats = await run_in_threadpool(
                query_by_status_stats_only,
                char_list=chars_unique,
                locations=locations,
                features=features,
                db_path=dialects_db
            )
            if fresh_stats:
                await set_cache(stats_key, fresh_stats, expire_seconds=120)
            return fresh_stats or {}

        async def _resolve_locations():
            location_payload = {
                "regions": payload.regions,
                "locations": payload.locations,
                "region_mode": payload.region_mode,
                "query_db": query_db
            }
            location_key = "compare_zhonggu_locations:" + hashlib.sha256(
                json.dumps(location_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest()
            cached_locations = await get_cache(location_key)
            if isinstance(cached_locations, list):
                return cached_locations

            fresh_locations = await run_in_threadpool(
                query_dialect_abbreviations,
                payload.regions,
                payload.locations,
                db_path=query_db,
                region_mode=payload.region_mode
            )
            if fresh_locations:
                await set_cache(location_key, fresh_locations, expire_seconds=60)
            return fresh_locations or []

        # === Step 1 & 2: 并行查询两组汉字（含缓存） ===
        cached_char_result1, cached_char_result2 = await asyncio.gather(
            _resolve_chars(
                payload.path_strings1,
                payload.column1,
                payload.combine_query1,
                payload.exclude_columns1
            ),
            _resolve_chars(
                payload.path_strings2,
                payload.column2,
                payload.combine_query2,
                payload.exclude_columns2
            )
        )

        if not cached_char_result1:
            return {
                "status": "empty",
                "message": "第一组无符合条件的汉字",
                "data": []
            }

        if not cached_char_result2:
            return {
                "status": "empty",
                "message": "第二组无符合条件的汉字",
                "data": []
            }

        # === Step 3: 处理地点 ===
        locations_processed = await _resolve_locations()

        if not locations_processed:
            return {
                "status": "error",
                "message": "无效的地点或分区",
                "data": []
            }

        # === Step 4: 收集所有汉字 ===
        chars1 = []
        for item in cached_char_result1:
            chars1.extend(item.get('汉字', []))

        chars2 = []
        for item in cached_char_result2:
            chars2.extend(item.get('汉字', []))

        chars1_unique = list(dict.fromkeys(chars1))
        chars2_unique = list(dict.fromkeys(chars2))

        # === Step 5 & 6: 轻量级统计查询（含短TTL缓存） ===
        stats1, stats2 = await asyncio.gather(
            _resolve_stats(chars1_unique, locations_processed, payload.features),
            _resolve_stats(chars2_unique, locations_processed, payload.features)
        )

        # === Step 7: 组织响应数据 ===
        comparison = []
        for loc in locations_processed:
            location_data = {
                "location": loc,
                "features": {}
            }

            for feature in payload.features:
                location_data["features"][feature] = {
                    "group1": stats1.get(loc, {}).get(feature, {"values": [], "total": 0}),
                    "group2": stats2.get(loc, {}).get(feature, {"values": [], "total": 0})
                }

            comparison.append(location_data)

        return {
            "status": "success",
            "group1": {
                "conditions": payload.path_strings1,
                "total_chars": len(set(chars1))
            },
            "group2": {
                "conditions": payload.path_strings2,
                "total_chars": len(set(chars2))
            },
            "comparison": comparison
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"compare_zhonggu failed: {e}")
    finally:
        print("compare_zhonggu")



