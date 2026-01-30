import re
import sqlite3

from sqlalchemy.orm import Session

from app.auth.models import User
from app.custom.models import Information
from common.getloc_by_name_region import query_dialect_abbreviations_orm


def get_from_submission(locations, regions, need_features, user: User, db: Session):
    # 获取 all_locations
    all_locations = query_dialect_abbreviations_orm(db, user, regions, locations)

    # 创建一个空的列表来存储结果
    result = []

    for location in all_locations:
        for feature in need_features:
            # 使用 ORM 查询，按 user_id、location 和 feature 进行过滤
            records = db.query(Information).filter(
                Information.user_id == user.id,
                Information.簡稱 == location,
                Information.特徵 == feature
            ).all()

            # 处理查询结果并添加到结果列表
            for record in records:
                # 解析經緯度，将字符串 "40.7128, -74.0060" 转换为列表 [40.7128, -74.0060]
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

    # 返回所有匹配到的结果
    return result
