"""Compatibility adapters: timestamps must resolve to exactly one owned record."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.schemas.user.submissions import CustomDataRecord
from app.service.user.core.models import Information
from app.service.user.submission.mutations import (
    check_create_quota, mutation_error, write_transaction,
)

FIELDS = ('簡稱', '音典分區', '經緯度', '聲韻調', '特徵', '值', '說明')
REQUIRED = ('簡稱', '音典分區', '經緯度', '特徵', '值')


def utc_timestamp(value):
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            mutation_error(422, 'validation_error', '创建时间格式无效')
    if value is None:
        mutation_error(422, 'validation_error', '创建时间不能为空')
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def require_unambiguous(records):
    if not records:
        mutation_error(404, 'record_unavailable', '记录不存在或无权访问')
    if len(records) != 1:
        mutation_error(409, 'ambiguous_identity', '创建时间对应多条记录，请刷新后使用 ID 操作')
    return records[0]


def require_fields(values):
    if not all(isinstance(values.get(field), str) and values[field].strip() for field in REQUIRED):
        mutation_error(422, 'validation_error', '必填字段不能为空')


def create_legacy(user, infos, session_factory):
    from app.service.user.submission.submit import get_max_value
    if not 1 <= len(infos) <= 50:
        mutation_error(422, 'validation_error', '单次提交必须为 1 至 50 条')
    items = [{field: getattr(info, field) for field in FIELDS} for info in infos]
    for item in items:
        require_fields(item)
    with write_transaction(session_factory) as db:
        check_create_quota(db, user, len(items))
        base_time = datetime.utcnow()
        records = []
        for index, item in enumerate(items):
            record = Information(**item, user_id=user.id, username=user.username,
                                 maxValue=get_max_value(item['值']),
                                 created_at=base_time + timedelta(milliseconds=index * 50))
            db.add(record)
            records.append(record)
        db.flush()
        data = [CustomDataRecord.model_validate(record).model_dump(mode='json') for record in records]
    return {'message': f'成功創建 {len(data)} 條記錄', 'data': data}


def edit_legacy(user, request, session_factory):
    from app.service.user.submission.submit import get_max_value
    with write_transaction(session_factory) as db:
        rows = db.scalars(select(Information).where(
            Information.user_id == user.id,
            Information.created_at == utc_timestamp(request.created_at),
        ).limit(2)).all()
        record = require_unambiguous(rows)
        changed = request.model_dump(exclude={'created_at'}, exclude_none=True)
        values = {field: changed.get(field, getattr(record, field)) for field in FIELDS}
        require_fields(values)
        for field, value in changed.items():
            setattr(record, field, value)
        if '值' in changed:
            record.maxValue = get_max_value(record.值)
        db.flush()
        result = CustomDataRecord.model_validate(record).model_dump(mode='json')
    return {'message': '更新成功', 'data': result}


def delete_legacy(user, timestamps, session_factory):
    targets = list(dict.fromkeys(utc_timestamp(value) for value in timestamps))
    if not 1 <= len(targets) <= 50:
        mutation_error(422, 'validation_error', '单次删除必须为 1 至 50 条')
    with write_transaction(session_factory) as db:
        # At most 51 rows are needed to reject a request that could affect >50 rows.
        rows = db.scalars(select(Information).where(
            Information.user_id == user.id, Information.created_at.in_(targets),
        ).limit(51)).all()
        counts = {timestamp: 0 for timestamp in targets}
        for row in rows:
            counts[row.created_at] += 1
        if any(count > 1 for count in counts.values()):
            mutation_error(409, 'ambiguous_identity', '创建时间不唯一，请刷新后使用 ID 操作')
        if any(count != 1 for count in counts.values()):
            mutation_error(404, 'record_unavailable', '部分记录已不可用，请刷新后核对')
        data = [CustomDataRecord.model_validate(row).model_dump(mode='json') for row in rows]
        for row in rows:
            db.delete(row)
    return {'message': f'成功刪除 {len(data)} 條記錄', 'deleted_count': len(data), 'deleted_records': data}
