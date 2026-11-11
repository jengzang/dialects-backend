"""Atomic bounded SQLite writes. Session factories are injected; no database globals."""
from contextlib import contextmanager
from datetime import timedelta
import hashlib
import json

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.exc import OperationalError

from app.common.time_utils import now_utc_naive
from app.schemas.user.custom_mutations import EditableFields
from app.schemas.user.submissions import CustomDataRecord
from app.service.user.core.models import CustomMutationReceipt, Information
from app.service.user.submission.write_limits import write_gate

HOURLY_RECORD_LIMIT = 500
TOTAL_RECORD_LIMIT = 5000
USER_RECEIPT_LIMIT = 200
GLOBAL_RECEIPT_LIMIT = 5000
RECEIPT_TTL = timedelta(hours=24)
RESULT_MAX_BYTES = 8192
EDITABLE_FIELDS = tuple(EditableFields.model_fields)


def mutation_error(status, code, message):
    raise HTTPException(status, detail={'code': code, 'message': message},
                        headers={'Retry-After': '1'} if status in (429,503) else None)


@contextmanager
def write_transaction(session_factory):
    """Gate before opening a Session; acquire SQLite's writer lock before reads."""
    with write_gate():
        db = session_factory()
        try:
            db.execute(text('BEGIN IMMEDIATE'))
            yield db
            db.commit()
        except OperationalError as exc:
            db.rollback()
            error = str(exc.orig).lower()
            if ('no such column' in error and 'version' in error) or ('no such table' in error and ('custom_mutation_receipts' in error or 'informations' in error)):
                mutation_error(503, 'migration_required', '数据结构待升级，请联系管理员')
            if 'locked' in error or 'busy' in error:
                mutation_error(503, 'database_busy', '数据库繁忙，请稍后重试')
            raise
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()


def check_create_quota(db, user, create_count, delete_count=0):
    """Caller must hold BEGIN IMMEDIATE across check and insertion."""
    if not create_count or user.role == 'admin':
        return
    now = now_utc_naive()
    total = db.scalar(select(func.count()).select_from(Information).where(Information.user_id == user.id))
    recent = db.scalar(select(func.count()).select_from(Information).where(
        Information.user_id == user.id, Information.created_at >= now - timedelta(hours=1)))
    if total - delete_count + create_count > TOTAL_RECORD_LIMIT or recent + create_count > HOURLY_RECORD_LIMIT:
        mutation_error(429, 'quota_exceeded', '已达到每小时 500 条或总量 5000 条限制')


def _owned_rows(db, user, ids):
    if not ids:
        return {}
    rows = db.scalars(select(Information).where(Information.user_id == user.id, Information.id.in_(ids))).all()
    if len(rows) != len(ids):
        mutation_error(404, 'record_unavailable', '部分记录已不可用，请刷新后核对')
    return {row.id: row for row in rows}


def _check_versions(rows, items):
    if any(rows[item.id].version != item.version for item in items):
        mutation_error(409, 'version_conflict', '记录已被修改，请刷新后核对')


def _apply_updates(rows, items):
    # Imported at call time so legacy submit may reuse this transaction module.
    from app.service.user.submission.submit import get_max_value
    for item in items:
        row = rows[item.id]
        if row.值 != item.值:
            row.maxValue = get_max_value(item.值)
        for field in EDITABLE_FIELDS:
            setattr(row, field, getattr(item, field))
        # Even an identical explicit edit advances the protocol version.
        row.version += 1


def batch_update(user, request, session_factory):
    with write_transaction(session_factory) as db:
        rows = _owned_rows(db, user, [item.id for item in request.items])
        _check_versions(rows, request.items)
        _apply_updates(rows, request.items)
        db.flush()
        data = [CustomDataRecord.model_validate(rows[item.id]).model_dump(mode='json') for item in request.items]
        result = {'success': True, 'updated_count': len(data), 'data': data}
    return result


def batch_delete_by_id(user, request, session_factory):
    ids = request.ids if request.ids is not None else [item.id for item in request.items]
    with write_transaction(session_factory) as db:
        rows = _owned_rows(db, user, ids)
        if request.items is not None:
            _check_versions(rows, request.items)
        for record_id in ids:
            db.delete(rows[record_id])
    return {'success': True, 'deleted_count': len(ids), 'deleted_ids': ids}


def save_custom_data(user, request, session_factory):
    digest = hashlib.sha256(json.dumps(request.model_dump(mode='json'), sort_keys=True,
                                      separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    request_id = str(request.request_id)
    with write_transaction(session_factory) as db:
        now = now_utc_naive()
        receipt = db.scalar(select(CustomMutationReceipt).where(
            CustomMutationReceipt.user_id == user.id, CustomMutationReceipt.request_id == request_id))
        if receipt is not None:
            if receipt.created_at < now - RECEIPT_TTL:
                mutation_error(409, 'idempotency_conflict', '请求确认期限已过，请重新读取并核对')
            if receipt.request_hash != digest:
                mutation_error(409, 'idempotency_conflict', '同一请求编号的内容发生变化')
            return json.loads(receipt.result_json)
        # Expired entries are only removed by explicit bounded maintenance, never by request scans.
        own_count = db.scalar(select(func.count()).select_from(CustomMutationReceipt).where(CustomMutationReceipt.user_id == user.id))
        total_count = db.scalar(select(func.count()).select_from(CustomMutationReceipt))
        if own_count >= USER_RECEIPT_LIMIT or total_count >= GLOBAL_RECEIPT_LIMIT:
            mutation_error(429, 'write_capacity_exceeded', '保存确认容量已满，请稍后重试')
        rows = _owned_rows(db, user, [item.id for item in [*request.updates, *request.deletes]])
        _check_versions(rows, [*request.updates, *request.deletes])
        check_create_quota(db, user, len(request.creates), len(request.deletes))
        _apply_updates(rows, request.updates)
        for item in request.deletes:
            db.delete(rows[item.id])
        from app.service.user.submission.submit import get_max_value
        created = []
        for item in request.creates:
            row = Information(**item.model_dump(exclude={'client_row_id'}), user_id=user.id,
                              username=user.username, 存儲標記=1, maxValue=get_max_value(item.值), created_at=now)
            db.add(row)
            created.append((item.client_row_id, row))
        db.flush()
        result = {'success': True, 'request_id': request_id,
                  'created_count': len(created), 'updated_count': len(request.updates), 'deleted_count': len(request.deletes),
                  'created': [{'client_row_id': key, 'id': row.id} for key, row in created],
                  'updated_ids': [item.id for item in request.updates], 'deleted_ids': [item.id for item in request.deletes]}
        result_json = json.dumps(result, ensure_ascii=False, separators=(',', ':'))
        if len(result_json.encode()) > RESULT_MAX_BYTES:
            mutation_error(422, 'validation_error', '保存结果过大，请缩小批次')
        db.add(CustomMutationReceipt(user_id=user.id, request_id=request_id, request_hash=digest,
                                     result_json=result_json, created_at=now))
    return result


def cleanup_expired_receipts(session_factory, limit=100):
    """Explicit maintenance command; at most 100 deletions in one short transaction."""
    limit = max(0, min(int(limit), 100))
    with write_transaction(session_factory) as db:
        rows = db.scalars(select(CustomMutationReceipt).where(
            CustomMutationReceipt.created_at < now_utc_naive() - RECEIPT_TTL
        ).order_by(CustomMutationReceipt.created_at).limit(limit)).all()
        for row in rows:
            db.delete(row)
    return len(rows)
