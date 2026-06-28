import re
from typing import List, Optional

from sqlalchemy.orm import Session

from app.service.auth.database.models import User
from app.service.user.core.models import Information
from app.service.geo.getloc_by_name_region import query_dialect_abbreviations_orm


def _dedupe_keep_order(items):
    seen = set()
    result = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _split_location_inputs(locations):
    parts = []
    for location in locations or []:
        if not isinstance(location, str):
            continue
        parts.extend(part.strip() for part in re.split(r"[ ,;/，；、]+", location) if part.strip())
    return _dedupe_keep_order(parts)


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

    - need_features: 过滤 Information.特徵（来自 ZhongGu path/query）
    - phonology_list: 若提供，额外过滤 Information.聲韻調（如 "聲母/韻母/聲調"）
    """
    if user is None:
        return []

    user_custom_locations = {
        row[0]
        for row in db.query(Information.簡稱)
        .filter(Information.user_id == user.id)
        .distinct()
        .all()
    }
    normalized_locations = _split_location_inputs(locations)
    direct_custom_locations = [loc for loc in normalized_locations if loc in user_custom_locations]
    region_custom_locations = query_dialect_abbreviations_orm(db, user, regions, [])
    all_locations = _dedupe_keep_order(region_custom_locations + direct_custom_locations)
    result = []

    for location in all_locations:
        q = db.query(Information).filter(
            Information.user_id == user.id,
            Information.簡稱 == location,
            Information.特徵.in_(need_features),
        )

        if phonology_list:
            q = q.filter(Information.聲韻調.in_(phonology_list))

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
