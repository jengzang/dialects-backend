import re
from typing import List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.service.auth.database.models import User
from app.service.user.core.models import Information
from app.service.geo.getloc_by_name_region import query_dialect_abbreviations_orm


def get_from_submission(
    locations,
    regions,
    need_features,
    user: Optional[User],
    db: Session,
    phonology_list: Optional[List[str]] = None,
):
    """
    查询用户自定义数据。

    - need_features: 过滤 Information.特徵（特征类型，如"韻母"）
    - phonology_list: 若提供，额外过滤 Information.聲韻調（音系分类，如"流摄"）
                      使用 LIKE 前缀匹配，兼容"流"/"流摄"/"流攝"等格式差异
    """
    if user is None:
        return []

    all_locations = query_dialect_abbreviations_orm(db, user, regions, locations)
    result = []

    for location in all_locations:
        q = db.query(Information).filter(
            Information.user_id == user.id,
            Information.簡稱 == location,
            Information.特徵.in_(need_features),
        )

        if phonology_list:
            q = q.filter(or_(*[Information.聲韻調.like(f"{p}%") for p in phonology_list]))

        for record in q.all():
            latitude_longitude = list(map(float, re.split(r'[，,]', record.經緯度)))
            result.append({
                "簡稱": record.簡稱,
                "聲韻調": record.聲韻調,
                "特徵": record.特徵,
                "值": record.值,
                "maxValue": record.maxValue,
                "經緯度": latitude_longitude,
                "說明": record.說明,
                "created_at": record.created_at,
            })

    return result
