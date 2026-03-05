"""
[PKG] 路由模块：字音比较 API
"""

from fastapi import APIRouter, Query, Depends
from typing import List, Optional
from sqlalchemy.orm import Session

from app.auth.database import get_db
from app.sql.db_selector import get_dialects_db, get_query_db
# from app.auth.dependencies import get_current_user
# from app.logging.dependencies.limiter import ApiLimiter
# from app.auth.models import User
from app.service.match_input_tip import match_locations_batch_all
from app.service.compare import compare_characters
from app.service.compare_tones import compare_tones
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
    query_db: str = Depends(get_query_db)
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
        locations_processed = match_locations_batch_all(
            locations or [],
            filter_valid_abbrs_only=True,
            exact_only=True,
            query_db=query_db,
            db=db,
            user=None  # 不再需要 user 对象
        )

        # 执行比较
        result = compare_characters(
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
    query_db: str = Depends(get_query_db)
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
        locations_processed = match_locations_batch_all(
            locations or [],
            filter_valid_abbrs_only=True,
            exact_only=True,
            query_db=query_db,
            db=db,
            user=None  # 不再需要 user 对象
        )

        # 执行比较
        result = compare_tones(
            tone_classes=tone_classes,
            locations=locations_processed,
            regions=regions,
            db_path=query_db,
            region_mode=region_mode
        )

        return {"results": result}

    finally:
        print("compare_tones")
