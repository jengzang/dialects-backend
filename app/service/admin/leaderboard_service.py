"""
Admin leaderboard service for calculating global rankings.

This module provides comprehensive ranking calculations for:
- User global rankings (aggregated across all APIs)
- User rankings by specific API
- API endpoint rankings
- Online time rankings
"""

from typing import List, Tuple, Literal
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.service.auth import models


def get_user_global_ranking(
    db: Session,
    metric: Literal["count", "duration", "upload", "download"],
    page: int,
    page_size: int
) -> Tuple[List[dict], int, float]:
    """
    获取用户全局排行（所有API汇总）

    Args:
        db: Database session
        metric: 指标类型
        page: 页码
        page_size: 每页数量

    Returns:
        (rankings, total_count, total_value)
    """
    # 映射指标到数据库字段
    metric_map = {
        "count": func.sum(models.ApiUsageSummary.count),
        "duration": func.sum(models.ApiUsageSummary.total_duration),
        "upload": func.sum(models.ApiUsageSummary.total_upload),
        "download": func.sum(models.ApiUsageSummary.total_download)
    }

    metric_col = metric_map[metric]

    # 子查询：每个用户的汇总值
    user_totals = db.query(
        models.ApiUsageSummary.user_id,
        models.User.username,
        metric_col.label("total_value")
    ).join(
        models.User,
        models.ApiUsageSummary.user_id == models.User.id
    ).group_by(
        models.ApiUsageSummary.user_id,
        models.User.username
    ).subquery()

    # 总数
    total_count = db.query(func.count()).select_from(user_totals).scalar() or 0

    # 计算所有用户的累计总量
    total_value = db.query(func.sum(user_totals.c.total_value)).scalar() or 0

    # 获取第一名的值（用于计算百分比）
    first_place_value = db.query(func.max(user_totals.c.total_value)).scalar() or 0

    # 分页查询
    results = db.query(user_totals).order_by(
        desc(user_totals.c.total_value)
    ).offset((page - 1) * page_size).limit(page_size).all()

    # 计算排名和百分比
    rankings = []
    for idx, row in enumerate(results):
        # 计算实际排名（考虑相同值）
        rank = db.query(func.count()).select_from(user_totals).filter(
            user_totals.c.total_value > row.total_value
        ).scalar() + 1

        # 计算与前一名的差距
        if rank == 1:
            gap_to_prev = None
        else:
            prev_value = db.query(user_totals.c.total_value).filter(
                user_totals.c.total_value > row.total_value
            ).order_by(user_totals.c.total_value.asc()).first()
            gap_to_prev = prev_value[0] - row.total_value if prev_value else None

        # 计算百分比
        percentage = (row.total_value / first_place_value * 100) if first_place_value > 0 else 0

        rankings.append({
            "rank": rank,
            "user_id": row.user_id,
            "username": row.username,
            "value": float(row.total_value or 0),
            "percentage": round(percentage, 2),
            "gap_to_prev": float(gap_to_prev) if gap_to_prev is not None else None,
            "first_place_value": float(first_place_value)
        })

    return rankings, total_count, float(total_value)


def get_user_by_api_ranking(
    db: Session,
    api_path: str,
    metric: Literal["count", "duration", "upload", "download"],
    page: int,
    page_size: int
) -> Tuple[List[dict], int, float]:
    """
    获取单个API的用户排行

    Args:
        db: Database session
        api_path: API路径
        metric: 指标类型
        page: 页码
        page_size: 每页数量

    Returns:
        (rankings, total_count, total_value)
    """
    # 映射指标到数据库字段
    metric_map = {
        "count": models.ApiUsageSummary.count,
        "duration": models.ApiUsageSummary.total_duration,
        "upload": models.ApiUsageSummary.total_upload,
        "download": models.ApiUsageSummary.total_download
    }

    metric_col = metric_map[metric]

    # 查询该API的所有用户数据
    query = db.query(
        models.ApiUsageSummary.user_id,
        models.User.username,
        metric_col.label("value")
    ).join(
        models.User,
        models.ApiUsageSummary.user_id == models.User.id
    ).filter(
        models.ApiUsageSummary.path == api_path
    )

    # 总数
    total_count = query.count()

    # 计算该API所有用户的累计总量
    total_value = db.query(func.sum(metric_col)).filter(
        models.ApiUsageSummary.path == api_path
    ).scalar() or 0

    # 获取第一名的值
    first_place_value = db.query(func.max(metric_col)).filter(
        models.ApiUsageSummary.path == api_path
    ).scalar() or 0

    # 分页查询
    results = query.order_by(desc(metric_col)).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    # 计算排名和百分比
    rankings = []
    for row in results:
        # 计算实际排名
        rank = db.query(func.count(models.ApiUsageSummary.user_id)).filter(
            models.ApiUsageSummary.path == api_path,
            metric_col > row.value
        ).scalar() + 1

        # 计算与前一名的差距
        if rank == 1:
            gap_to_prev = None
        else:
            prev_value = db.query(metric_col).filter(
                models.ApiUsageSummary.path == api_path,
                metric_col > row.value
            ).order_by(metric_col.asc()).first()
            gap_to_prev = prev_value[0] - row.value if prev_value else None

        # 计算百分比
        percentage = (row.value / first_place_value * 100) if first_place_value > 0 else 0

        rankings.append({
            "rank": rank,
            "user_id": row.user_id,
            "username": row.username,
            "value": float(row.value or 0),
            "percentage": round(percentage, 2),
            "gap_to_prev": float(gap_to_prev) if gap_to_prev is not None else None,
            "first_place_value": float(first_place_value)
        })

    return rankings, total_count, float(total_value)


def get_api_ranking(
    db: Session,
    metric: Literal["count", "duration", "upload", "download"],
    page: int,
    page_size: int
) -> Tuple[List[dict], int, float]:
    """
    获取API端点排行

    Args:
        db: Database session
        metric: 指标类型
        page: 页码
        page_size: 每页数量

    Returns:
        (rankings, total_count, total_value)
    """
    # 映射指标到数据库字段
    metric_map = {
        "count": func.sum(models.ApiUsageSummary.count),
        "duration": func.sum(models.ApiUsageSummary.total_duration),
        "upload": func.sum(models.ApiUsageSummary.total_upload),
        "download": func.sum(models.ApiUsageSummary.total_download)
    }

    metric_col = metric_map[metric]

    # 子查询：每个API的汇总值
    api_totals = db.query(
        models.ApiUsageSummary.path,
        metric_col.label("total_value"),
        func.count(func.distinct(models.ApiUsageSummary.user_id)).label("unique_users")
    ).group_by(
        models.ApiUsageSummary.path
    ).subquery()

    # 总数
    total_count = db.query(func.count()).select_from(api_totals).scalar() or 0

    # 计算所有API的累计总量
    total_value = db.query(func.sum(api_totals.c.total_value)).scalar() or 0

    # 获取第一名的值
    first_place_value = db.query(func.max(api_totals.c.total_value)).scalar() or 0

    # 分页查询
    results = db.query(api_totals).order_by(
        desc(api_totals.c.total_value)
    ).offset((page - 1) * page_size).limit(page_size).all()

    # 计算排名和百分比
    rankings = []
    for row in results:
        # 计算实际排名
        rank = db.query(func.count()).select_from(api_totals).filter(
            api_totals.c.total_value > row.total_value
        ).scalar() + 1

        # 计算与前一名的差距
        if rank == 1:
            gap_to_prev = None
        else:
            prev_value = db.query(api_totals.c.total_value).filter(
                api_totals.c.total_value > row.total_value
            ).order_by(api_totals.c.total_value.asc()).first()
            gap_to_prev = prev_value[0] - row.total_value if prev_value else None

        # 计算百分比
        percentage = (row.total_value / first_place_value * 100) if first_place_value > 0 else 0

        rankings.append({
            "rank": rank,
            "path": row.path,
            "value": float(row.total_value or 0),
            "percentage": round(percentage, 2),
            "unique_users": row.unique_users,
            "gap_to_prev": float(gap_to_prev) if gap_to_prev is not None else None,
            "first_place_value": float(first_place_value)
        })

    return rankings, total_count, float(total_value)


def get_online_time_ranking(
    db: Session,
    page: int,
    page_size: int
) -> Tuple[List[dict], int, float]:
    """
    获取在线时长排行

    Args:
        db: Database session
        page: 页码
        page_size: 每页数量

    Returns:
        (rankings, total_count, total_value)
    """
    # 查询所有有在线时长的用户
    query = db.query(
        models.User.id,
        models.User.username,
        models.User.total_online_seconds
    ).filter(
        models.User.total_online_seconds > 0
    )

    # 总数
    total_count = query.count()

    # 计算所有用户的在线时长累计总量
    total_value = db.query(func.sum(models.User.total_online_seconds)).filter(
        models.User.total_online_seconds > 0
    ).scalar() or 0

    # 获取第一名的值
    first_place_value = db.query(func.max(models.User.total_online_seconds)).scalar() or 0

    # 分页查询
    results = query.order_by(
        desc(models.User.total_online_seconds)
    ).offset((page - 1) * page_size).limit(page_size).all()

    # 计算排名和百分比
    rankings = []
    for row in results:
        # 计算实际排名
        rank = db.query(func.count(models.User.id)).filter(
            models.User.total_online_seconds > row.total_online_seconds
        ).scalar() + 1

        # 计算与前一名的差距
        if rank == 1:
            gap_to_prev = None
        else:
            prev_value = db.query(models.User.total_online_seconds).filter(
                models.User.total_online_seconds > row.total_online_seconds
            ).order_by(models.User.total_online_seconds.asc()).first()
            gap_to_prev = prev_value[0] - row.total_online_seconds if prev_value else None

        # 计算百分比
        percentage = (row.total_online_seconds / first_place_value * 100) if first_place_value > 0 else 0

        rankings.append({
            "rank": rank,
            "user_id": row.id,
            "username": row.username,
            "value": float(row.total_online_seconds or 0),
            "percentage": round(percentage, 2),
            "gap_to_prev": float(gap_to_prev) if gap_to_prev is not None else None,
            "first_place_value": float(first_place_value)
        })

    return rankings, total_count, float(total_value)


def get_available_apis(db: Session) -> List[str]:
    """
    获取所有可用的API路径

    Args:
        db: Database session

    Returns:
        API路径列表
    """
    results = db.query(
        models.ApiUsageSummary.path
    ).distinct().order_by(
        models.ApiUsageSummary.path
    ).all()

    return [row[0] for row in results]

