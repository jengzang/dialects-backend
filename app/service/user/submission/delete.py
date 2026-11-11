"""Legacy form deletion only accepts one unambiguous owned match."""
from sqlalchemy.orm import Session

from app.service.auth.database.models import User
from app.service.user.core.models import Information
from app.service.user.submission.legacy_mutations import utc_timestamp, require_unambiguous
from app.service.user.submission.mutations import write_transaction


def handle_form_deletion(form_data: dict, user: User, db: Session):
    location, feature, value = (form_data.get(key) for key in ('location', 'feature', 'value'))
    if not location or not feature or not value:
        return {"success": False, "message": "地点、特征和值不能为空"}
    timestamp = utc_timestamp(form_data.get('created_at'))
    with write_transaction(lambda: db):
        query = db.query(Information).filter(
            Information.user_id == user.id, Information.簡稱 == location,
            Information.特徵 == feature, Information.值 == value,
            Information.created_at == timestamp,
        )
        if form_data.get('phonology'):
            query = query.filter(Information.聲韻調 == form_data['phonology'])
        record = require_unambiguous(query.limit(2).all())
        message = f"已删除：{record.簡稱} {record.音典分區} {record.聲韻調 or ''} {record.特徵} {record.值} {record.說明 or ''}"
        db.delete(record)
    return {"success": True, "message": message}
