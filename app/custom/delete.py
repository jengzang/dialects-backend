import json

from sqlalchemy.orm import Session, class_mapper

from app.auth.models import User
from app.custom.models import Information


def handle_form_deletion(form_data: dict, user: User, db: Session):
    # 取得表單資料
    location = form_data.get('location')
    # region = form_data.get('region', None)
    # coordinates = form_data.get('coordinates', None)
    feature = form_data.get('feature')
    value = form_data.get('value')
    # description = form_data.get('description', None)
    created_at = form_data.get('created_at')
    if created_at:
        created_at = created_at.replace('T', ' ')

    if not location or not feature or not value:
        return {"success": False, "message": "[!] 程序出錯，地點/特徵/值存在空值"}

    # 查詢符合條件的紀錄
    records_to_delete = db.query(Information).filter(
        Information.user_id == user.id,
        Information.簡稱 == location,
        Information.特徵 == feature,
        Information.值 == value,
        Information.created_at == created_at
    ).all()

    if not records_to_delete:
        return {"success": False, "message": "[X] 找不到符合條件的資料以刪除"}

    def model_to_dict_non_empty(obj):
        return {
            column.key: getattr(obj, column.key)
            for column in class_mapper(obj.__class__).columns
            if (getattr(obj, column.key) not in (None, '', []) or column.key == '說明')
        }

    # 刪除找到的紀錄
    deleted_records = []

    for record in records_to_delete:
        deleted_records.append(model_to_dict_non_empty(record))
        db.delete(record)

    db.commit()
    # 刪除找到的紀錄
    deleted_records_str = "\n".join([
            f"{'地點':<15} {'音典分區':<20} {'經緯度':<20} {'聲韻調':<20} {'特徵':<20} {'值':<20} {'說明':<20}"
        ] + [
            # 处理 `說明` 为 `None` 的情况，使用空字符串代替
            f"{record.get('簡稱', ''):<15} {record.get('音典分區', ''):<20} {record.get('經緯度', ''):<20} "
            f"{record.get('聲韻調', ''):<20} {record.get('特徵', ''):<20} {record.get('值', ''):<20} {record.get('說明', '') or '無說明':<20}"
            for record in deleted_records
        ])

    return {
        "success": True,
        "message": f"[DEL] 詳細信息：\n{deleted_records_str}"
    }

