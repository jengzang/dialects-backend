# app/custom/region_service.py
"""
用户自定义区域服务层
提供 CRUD 操作：创建、更新、删除、查询自定义区域
"""
import json
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.service.user.submission.models import UserRegion


def create_or_update_region(
    db: Session,
    user_id: int,
    username: str,
    region_name: str,
    locations: List[str],
    description: Optional[str] = None
) -> tuple[UserRegion, str]:
    """
    创建或更新用户自定义区域

    Args:
        db: 数据库会话
        user_id: 用户ID
        username: 用户名
        region_name: 区域名称
        locations: 地点简称列表
        description: 区域描述（可选）

    Returns:
        (UserRegion对象, 操作类型: "created" 或 "updated")
    """
    # 查找是否已存在
    existing = db.query(UserRegion).filter(
        and_(
            UserRegion.user_id == user_id,
            UserRegion.region_name == region_name
        )
    ).first()

    # 将列表转换为 JSON 字符串
    locations_json = json.dumps(locations, ensure_ascii=False)

    if existing:
        # 更新现有记录
        existing.locations = locations_json
        existing.description = description
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing, "updated"
    else:
        # 创建新记录
        new_region = UserRegion(
            user_id=user_id,
            username=username,
            region_name=region_name,
            locations=locations_json,
            description=description
        )
        db.add(new_region)
        db.commit()
        db.refresh(new_region)
        return new_region, "created"


def delete_region(
    db: Session,
    user_id: int,
    region_name: str
) -> bool:
    """
    删除用户自定义区域

    Args:
        db: 数据库会话
        user_id: 用户ID
        region_name: 区域名称

    Returns:
        是否成功删除（True/False）
    """
    region = db.query(UserRegion).filter(
        and_(
            UserRegion.user_id == user_id,
            UserRegion.region_name == region_name
        )
    ).first()

    if region:
        db.delete(region)
        db.commit()
        return True
    return False


def get_user_regions(
    db: Session,
    user_id: int,
    region_name: Optional[str] = None
) -> List[dict]:
    """
    获取用户的自定义区域列表

    Args:
        db: 数据库会话
        user_id: 用户ID
        region_name: 可选，筛选特定区域名称

    Returns:
        区域字典列表，包含 location_count 字段
    """
    query = db.query(UserRegion).filter(UserRegion.user_id == user_id)

    if region_name:
        query = query.filter(UserRegion.region_name == region_name)

    regions = query.order_by(UserRegion.created_at.desc()).all()

    # 转换为字典并添加 location_count
    result = []
    for region in regions:
        locations = json.loads(region.locations)
        result.append({
            "id": region.id,
            "region_name": region.region_name,
            "locations": locations,
            "location_count": len(locations),
            "description": region.description,
            "created_at": region.created_at,
            "updated_at": region.updated_at
        })

    return result


# ===== Admin Functions =====

def get_all_regions_admin(
    db: Session,
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None
) -> tuple[List[dict], int]:
    """获取所有区域（管理员视图），支持分页和搜索"""
    query = db.query(UserRegion)

    if search:
        query = query.filter(
            (UserRegion.username.contains(search)) |
            (UserRegion.region_name.contains(search))
        )

    total = query.count()
    regions = query.order_by(UserRegion.created_at.desc()).offset(skip).limit(limit).all()

    result = []
    for region in regions:
        locations = json.loads(region.locations)
        result.append({
            "id": region.id,
            "user_id": region.user_id,
            "username": region.username,
            "region_name": region.region_name,
            "locations": locations,
            "location_count": len(locations),
            "description": region.description,
            "created_at": region.created_at,
            "updated_at": region.updated_at
        })

    return result, total


def get_regions_by_username_admin(db: Session, username: str) -> List[dict]:
    """按用户名获取区域（管理员视图）"""
    regions = db.query(UserRegion).filter(UserRegion.username == username).order_by(UserRegion.created_at.desc()).all()

    result = []
    for region in regions:
        locations = json.loads(region.locations)
        result.append({
            "id": region.id,
            "region_name": region.region_name,
            "locations": locations,
            "location_count": len(locations),
            "description": region.description,
            "created_at": region.created_at,
            "updated_at": region.updated_at
        })

    return result


def get_user_region_counts(db: Session) -> List[dict]:
    """获取每个用户的区域数量"""
    from sqlalchemy import func

    counts = db.query(
        UserRegion.username,
        func.count(UserRegion.id).label('region_count')
    ).group_by(UserRegion.username).all()

    return [{"username": username, "region_count": count} for username, count in counts]


def get_region_statistics(db: Session) -> dict:
    """获取区域统计信息"""
    from sqlalchemy import func
    from collections import Counter

    # 基础统计
    total_regions = db.query(func.count(UserRegion.id)).scalar()
    total_users = db.query(func.count(func.distinct(UserRegion.user_id))).scalar()

    # 所有区域的地点
    all_regions = db.query(UserRegion.locations).all()
    all_locations = []
    for (locations_json,) in all_regions:
        all_locations.extend(json.loads(locations_json))

    total_locations = len(set(all_locations))
    avg_locations = len(all_locations) / total_regions if total_regions > 0 else 0

    # 用户统计（前10）
    user_stats = db.query(
        UserRegion.username,
        func.count(UserRegion.id).label('region_count')
    ).group_by(UserRegion.username).order_by(func.count(UserRegion.id).desc()).limit(10).all()

    # 热门地点（前20）
    location_counter = Counter(all_locations)
    popular_locations = [
        {"location": loc, "usage_count": count}
        for loc, count in location_counter.most_common(20)
    ]

    # 最近活动（最近10条）
    recent = db.query(UserRegion).order_by(UserRegion.updated_at.desc()).limit(10).all()
    recent_activity = [
        {
            "username": r.username,
            "region_name": r.region_name,
            "action": "updated" if r.updated_at > r.created_at else "created",
            "timestamp": r.updated_at.isoformat()
        }
        for r in recent
    ]

    return {
        "summary": {
            "total_regions": total_regions,
            "total_users": total_users,
            "total_locations": total_locations,
            "avg_locations_per_region": round(avg_locations, 2)
        },
        "user_stats": [{"username": u, "region_count": c} for u, c in user_stats],
        "popular_locations": popular_locations,
        "recent_activity": recent_activity
    }


def create_region_admin(
    db: Session,
    username: str,
    region_name: str,
    locations: List[str],
    description: Optional[str] = None
) -> UserRegion:
    """管理员为任意用户创建区域"""
    from app.service.auth.models import User
    from app.service.auth import SessionLocal as SessionLocal_user

    # 查找用户
    session_user = SessionLocal_user()
    try:
        user = session_user.query(User).filter(User.username == username).first()
        if not user:
            raise ValueError(f"用户 {username} 不存在")
        user_id = user.id
    finally:
        session_user.close()

    # 检查是否已存在
    existing = db.query(UserRegion).filter(
        and_(UserRegion.user_id == user_id, UserRegion.region_name == region_name)
    ).first()

    if existing:
        raise ValueError(f"用户 {username} 已有名为 {region_name} 的区域")

    # 创建新区域
    locations_json = json.dumps(locations, ensure_ascii=False)
    new_region = UserRegion(
        user_id=user_id,
        username=username,
        region_name=region_name,
        locations=locations_json,
        description=description
    )
    db.add(new_region)
    db.commit()
    db.refresh(new_region)
    return new_region


def update_region_admin(
    db: Session,
    username: str,
    region_name: str,
    new_region_name: Optional[str] = None,
    locations: Optional[List[str]] = None,
    description: Optional[str] = None
) -> UserRegion:
    """管理员更新任意用户的区域"""
    from app.service.auth.models import User
    from app.service.auth import SessionLocal as SessionLocal_user

    # 查找用户
    session_user = SessionLocal_user()
    try:
        user = session_user.query(User).filter(User.username == username).first()
        if not user:
            raise ValueError(f"用户 {username} 不存在")
        user_id = user.id
    finally:
        session_user.close()

    # 查找区域
    region = db.query(UserRegion).filter(
        and_(UserRegion.user_id == user_id, UserRegion.region_name == region_name)
    ).first()

    if not region:
        raise ValueError(f"用户 {username} 没有名为 {region_name} 的区域")

    # 更新字段
    if new_region_name:
        region.region_name = new_region_name
    if locations:
        region.locations = json.dumps(locations, ensure_ascii=False)
    if description is not None:
        region.description = description

    region.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(region)
    return region


def delete_region_admin(db: Session, username: str, created_at: str) -> bool:
    """管理员删除任意用户的区域"""
    from app.service.auth.models import User
    from app.service.auth import SessionLocal as SessionLocal_user

    # 查找用户
    session_user = SessionLocal_user()
    try:
        user = session_user.query(User).filter(User.username == username).first()
        if not user:
            raise ValueError(f"用户 {username} 不存在")
        user_id = user.id
    finally:
        session_user.close()

    # 查找并删除区域
    regions = db.query(UserRegion).filter(
        and_(UserRegion.user_id == user_id, UserRegion.created_at == created_at)
    ).all()

    if regions:
        for region in regions:
            db.delete(region)
        db.commit()
        return True
    return False


def batch_delete_regions_admin(db: Session, regions: List[dict]) -> tuple[int, List[dict]]:
    """批量删除区域（管理员操作）"""
    deleted_count = 0
    failed = []

    for item in regions:
        try:
            success = delete_region_admin(db, item["username"], item["created_at"])
            if success:
                deleted_count += 1
            else:
                failed.append({
                    "username": item["username"],
                    "created_at": item["created_at"],
                    "error": "区域不存在"
                })
        except Exception as e:
            failed.append({
                "username": item["username"],
                "created_at": item["created_at"],
                "error": str(e)
            })

    return deleted_count, failed

