#!/usr/bin/env python3
"""
批量修改路由文件，使用依赖注入封装数据库选择
"""
import re

def modify_file(filepath, modifications):
    """修改文件"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    for old, new in modifications:
        content = content.replace(old, new)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"✓ Modified {filepath}")

# compare.py
compare_mods = [
    # 修改导入
    (
        """from app.auth.database import get_db
from app.auth.dependencies import get_current_user
# from app.logging.dependencies.limiter import ApiLimiter
from app.auth.models import User""",
        """from app.auth.database import get_db
from app.sql.db_selector import get_dialects_db, get_query_db
# from app.auth.dependencies import get_current_user
# from app.logging.dependencies.limiter import ApiLimiter
# from app.auth.models import User"""
    ),
    # compare_chars 函数签名
    (
        """@router.get("/compare/chars")
async def compare_chars(
    chars: List[str] = Query(..., description="要比较的汉字列表，至少2个"),
    features: List[str] = Query(..., description="要比较的特征列表：聲母/韻母/聲調"),
    locations: Optional[List[str]] = Query(None, description="要查的地点，可多个"),
    regions: Optional[List[str]] = Query(None, description="要查的分区，可多个"),
    region_mode: str = Query("yindian", description="分区模式，可选 'yindian' 或 'map'"),
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user)
):""",
        """@router.get("/compare/chars")
async def compare_chars(
    chars: List[str] = Query(..., description="要比较的汉字列表，至少2个"),
    features: List[str] = Query(..., description="要比较的特征列表：聲母/韻母/聲調"),
    locations: Optional[List[str]] = Query(None, description="要查的地点，可多个"),
    regions: Optional[List[str]] = Query(None, description="要查的分区，可多个"),
    region_mode: str = Query("yindian", description="分区模式，可选 'yindian' 或 'map'"),
    db: Session = Depends(get_db),
    dialects_db: str = Depends(get_dialects_db),
    query_db: str = Depends(get_query_db)
):"""
    ),
    # compare_chars 函数体
    (
        """    try:
        # 处理地点输入（逻辑与 search_chars 完全一致）
        query_db = QUERY_DB_ADMIN if user and user.role == "admin" else QUERY_DB_USER
        locations_processed = match_locations_batch_all(
            locations or [],
            filter_valid_abbrs_only=True,
            exact_only=True,
            query_db=query_db,
            db=db,
            user=user
        )

        db_path = DIALECTS_DB_ADMIN if user and user.role == "admin" else DIALECTS_DB_USER

        # 执行比较
        result = compare_characters(
            chars=chars,
            features=features,
            locations=locations_processed,
            regions=regions,
            db_path=db_path,
            region_mode=region_mode,
            query_db_path=query_db
        )""",
        """    try:
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
        )"""
    ),
    # compare_tones_route 函数签名
    (
        """@router.get("/compare/tones")
async def compare_tones_route(
    tone_classes: List[int] = Query(..., description="要比较的调类编号列表，如 [1,2,3] 表示 T1,T2,T3"),
    locations: Optional[List[str]] = Query(None, description="要查的地点，可多个"),
    regions: Optional[List[str]] = Query(None, description="要查的分区，可多个"),
    region_mode: str = Query("yindian", description="分区模式，可选 'yindian' 或 'map'"),
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user)
):""",
        """@router.get("/compare/tones")
async def compare_tones_route(
    tone_classes: List[int] = Query(..., description="要比较的调类编号列表，如 [1,2,3] 表示 T1,T2,T3"),
    locations: Optional[List[str]] = Query(None, description="要查的地点，可多个"),
    regions: Optional[List[str]] = Query(None, description="要查的分区，可多个"),
    region_mode: str = Query("yindian", description="分区模式，可选 'yindian' 或 'map'"),
    db: Session = Depends(get_db),
    query_db: str = Depends(get_query_db)
):"""
    ),
    # compare_tones_route 函数体
    (
        """    try:
        # 处理地点输入（逻辑与 search_tones 完全一致）
        query_db = QUERY_DB_ADMIN if user and user.role == "admin" else QUERY_DB_USER
        locations_processed = match_locations_batch_all(
            locations or [],
            filter_valid_abbrs_only=True,
            exact_only=True,
            query_db=query_db,
            db=db,
            user=user
        )""",
        """    try:
        # 数据库路径已通过依赖注入自动选择
        # 处理地点输入（逻辑与 search_tones 完全一致）
        locations_processed = match_locations_batch_all(
            locations or [],
            filter_valid_abbrs_only=True,
            exact_only=True,
            query_db=query_db,
            db=db,
            user=None  # 不再需要 user 对象
        )"""
    ),
]

modify_file('app/routes/compare.py', compare_mods)
print("Done!")
