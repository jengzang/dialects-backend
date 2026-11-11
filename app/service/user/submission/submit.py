from datetime import datetime, timedelta
import re
from app.service.user.core.models import Information
from sqlalchemy.orm import Session
from app.service.auth.database.models import User


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
    from fastapi import HTTPException
    from app.service.user.submission.mutations import check_create_quota, write_transaction

    if user is None:
        raise HTTPException(401, detail="请先登录")
    fields = {
        '簡稱': form_data.get('location'), '音典分區': form_data.get('region'),
        '經緯度': form_data.get('coordinates'), '聲韻調': form_data.get('phonology'),
        '特徵': form_data.get('feature'), '值': form_data.get('value'),
        '說明': form_data.get('description'),
    }
    if not all(isinstance(fields[key], str) and fields[key].strip() for key in fields if key != '說明'):
        return {"success": False, "message": "所有字段（除说明）必须填写"}
    with write_transaction(lambda: db):
        check_create_quota(db, user, 1)
        db.add(Information(**fields, user_id=user.id, username=user.username,
                           存儲標記=1, maxValue=get_max_value(fields['值']), created_at=datetime.utcnow()))
        db.flush()
        total = db.query(Information).filter(Information.user_id == user.id).count()
        recent = db.query(Information).filter(Information.user_id == user.id,
                    Information.created_at >= datetime.utcnow() - timedelta(hours=1)).count()
    return {"success": True, "message": f"提交成功，目前共有 {total} 份数据，本小时已提交 {recent} 份"}
