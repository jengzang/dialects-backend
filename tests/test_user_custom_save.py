import uuid
from datetime import timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import event

from app.common.time_utils import now_utc_naive
from app.service.user.core.models import Information, CustomMutationReceipt
from tests.test_user_custom_mutations import factory, FIELDS, USER, update_item


def request(**changes):
    from app.schemas.user.custom_mutations import SaveCustomDataRequest
    return SaveCustomDataRequest(request_id=uuid.uuid4(), **changes)


def test_same_request_replay_and_conflicting_content(factory):
    from app.service.user.submission.mutations import save_custom_data
    req=request(creates=[dict(FIELDS,client_row_id='draft-1')], updates=[update_item(值='66')],deletes=[dict(id=2,version=1)])
    first=save_custom_data(USER,req,factory)
    assert first==save_custom_data(USER,req,factory)
    assert first['created_count']==1 and first['deleted_count']==1 and first['updated_count']==1
    assert first['created'][0]['client_row_id']=='draft-1'
    conflict=req.model_copy(deep=True)
    conflict.creates[0].值='77'
    with pytest.raises(HTTPException) as error:
        save_custom_data(USER,conflict,factory)
    assert error.value.detail['code']=='idempotency_conflict'
    with factory() as db:
        assert db.query(Information).count()==3
        assert db.query(CustomMutationReceipt).count()==1


def test_save_mid_transaction_failure_rolls_back_receipt_and_data(factory):
    from app.service.user.submission.mutations import save_custom_data
    def explode(*args):
        raise RuntimeError('injected')
    event.listen(CustomMutationReceipt,'before_insert',explode)
    try:
        with pytest.raises(RuntimeError):
            save_custom_data(USER,request(creates=[dict(FIELDS,client_row_id='new')], updates=[update_item(值='66')],deletes=[dict(id=2,version=1)]),factory)
    finally:
        event.remove(CustomMutationReceipt,'before_insert',explode)
    with factory() as db:
        assert db.query(Information).count()==3
        assert db.get(Information,1).值=='55'
        assert db.get(Information,2)
        assert db.query(CustomMutationReceipt).count()==0


def test_receipt_capacity_and_expired_key(factory, monkeypatch):
    from app.service.user.submission import mutations
    monkeypatch.setattr(mutations,'USER_RECEIPT_LIMIT',1)
    req=request(creates=[dict(FIELDS,client_row_id='new')])
    mutations.save_custom_data(USER,req,factory)
    assert mutations.save_custom_data(USER,req,factory)['success']
    with pytest.raises(HTTPException) as error:
        mutations.save_custom_data(USER,request(creates=[dict(FIELDS,client_row_id='new2')]),factory)
    assert error.value.status_code==429
    with factory() as db:
        receipt=db.query(CustomMutationReceipt).one()
        receipt.created_at=now_utc_naive()-timedelta(hours=25)
        db.commit()
    with pytest.raises(HTTPException) as error:
        mutations.save_custom_data(USER,req,factory)
    assert error.value.detail['code']=='idempotency_conflict'


def test_create_quota_checked_inside_transaction(factory,monkeypatch):
    from app.service.user.submission import mutations
    monkeypatch.setattr(mutations,'TOTAL_RECORD_LIMIT',2)
    with pytest.raises(HTTPException) as error:
        mutations.save_custom_data(USER,request(creates=[dict(FIELDS,client_row_id='new')]),factory)
    assert error.value.detail['code']=='quota_exceeded'
    mutations.save_custom_data(USER,request(updates=[update_item(值='66')]),factory)


def test_replay_survives_fresh_session_factory(factory):
    from sqlalchemy.orm import sessionmaker
    from app.service.user.submission.mutations import save_custom_data
    req=request(creates=[dict(FIELDS,client_row_id='new')])
    result=save_custom_data(USER,req,factory)
    assert save_custom_data(USER,req,sessionmaker(bind=factory.kw['bind']))==result


def test_expired_receipt_cleanup_is_bounded(factory):
    from app.service.user.submission.mutations import cleanup_expired_receipts
    old=now_utc_naive()-timedelta(hours=25)
    with factory() as db:
        db.add_all([CustomMutationReceipt(user_id=1,request_id=str(uuid.uuid4()),request_hash='0'*64,result_json='{}',created_at=old) for _ in range(101)])
        db.add(CustomMutationReceipt(user_id=1,request_id=str(uuid.uuid4()),request_hash='0'*64,result_json='{}',created_at=now_utc_naive()))
        db.commit()
    assert cleanup_expired_receipts(factory,limit=1000)==100
    with factory() as db:
        assert db.query(CustomMutationReceipt).count()==2


def test_concurrent_request_rejected_before_session_then_replayed(factory):
    from threading import Event, Thread
    from app.service.user.submission.mutations import save_custom_data
    from app.service.user.submission.write_limits import write_gate
    acquired,release=Event(),Event()
    def hold_slot():
        with write_gate():
            acquired.set()
            release.wait(timeout=5)
    thread=Thread(target=hold_slot)
    thread.start()
    assert acquired.wait(timeout=5)
    opened=[]
    def forbidden_factory():
        opened.append(True)
        raise AssertionError('Session should not open while write slot occupied')
    req=request(creates=[dict(FIELDS,client_row_id='new')])
    try:
        with pytest.raises(HTTPException) as error:
            save_custom_data(USER,req,forbidden_factory)
        assert error.value.status_code==429
        assert not opened
    finally:
        release.set()
        thread.join(timeout=5)
    result=save_custom_data(USER,req,factory)
    assert save_custom_data(USER,req,factory)==result
