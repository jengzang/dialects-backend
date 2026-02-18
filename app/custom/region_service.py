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

from app.custom.models import UserRegion


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

