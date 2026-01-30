from datetime import datetime, timedelta
import re
from app.custom.models import Information
from sqlalchemy.orm import Session
from app.auth.models import User


def get_max_value(value: str):
    value = value.strip()
    if '(' not in value and ',' not in value and '/' not in value:
        return value
    if '(' not in value and (',' in value or '/' in value):
        return re.split('[,/]', value)[0]
    if '(' in value and ',' not in value and '/' not in value:
        match = re.search(r'\((.*?)\)', value)
        if match:
            return match.group(1).replace('*', '')
    if '(' in value and (',' in value or '/' in value):
        value = re.sub(r'\(.*?\)', '', value)
        return re.split('[,/]', value)[0]
    if '(' in value:
        value_outside = re.sub(r'\(.*?\)', '', value)
        return re.split('[,/]', value_outside)[0]
    return value
def handle_form_submission(form_data: dict, user: User, db: Session):
    # 取得表單資料
    location = form_data.get('location')
    region = form_data.get('region')
    coordinates = form_data.get('coordinates')
    phonology = form_data.get('phonology')
    feature = form_data.get('feature')
    value = form_data.get('value')
    description = form_data.get('description', None)

    if not location or not region or not coordinates or not phonology or not feature or not value:
        return {"success": False, "message": "[!] 所有字段（除說明）必須填寫！"}


    max_value = get_max_value(value)

    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    # 用戶限制（非管理員）
    if not user.role:
        count_last_hour = db.query(Information).filter(
            Information.user_id == user.id,
            Information.created_at >= one_hour_ago
        ).count()

        total_count = db.query(Information).filter(
            Information.user_id == user.id
        ).count()

        if count_last_hour >= 100:
            return {"success": False, "message": "💥 每小時最多提交 100 份資料"}
        if total_count >= 1000:
            return {"success": False, "message": "🚫 最多只能提交 1000 份資料"}

    # 寫入資料
    info = Information(
        簡稱=location,
        音典分區=region,
        經緯度=coordinates,
        聲韻調=phonology,
        特徵=feature,
        值=value,
        說明=description,
        存儲標記=1,
        maxValue=max_value,
        user_id=user.id,
        username=user.username,
        created_at=datetime.utcnow()
    )

    db.add(info)
    db.commit()

    # [OK] 再次查詢用戶目前的總提交數
    total_submitted = db.query(Information).filter(
        Information.user_id == user.id
    ).count()
    submitted_this_hour = db.query(Information).filter(
        Information.user_id == user.id,
        Information.created_at >= one_hour_ago
    ).count()

    return {
        "success": True,
        "message": (
            f"[DONE] 這是你提交的第 {total_submitted} 份數據！\n"
            f"[SAVE] 本小時已提交 {submitted_this_hour} 份數據。"
        )
    }


