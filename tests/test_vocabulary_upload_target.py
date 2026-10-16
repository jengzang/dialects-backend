import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.service.vocabulary.models import Base, VocabularyEntry as Entry, VocabularyLocation as Location, VocabularyLog, VocabularyPermission
from app.service.vocabulary.service import import_vocabulary_upload, preview_vocabulary_upload


@pytest.fixture
def db():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(VocabularyPermission(user_id=7, permission_level='edit'))
        for owner in [7, 8]:
            session.add(Location(user_id=owner, location_name='甲村', coordinates='113,23', province='广东', vocabulary_source='调查手稿', description='说明', other='其他', t1='55'))
            session.add(Entry(user_id=owner, location_name='甲村', standard_word='旧词', local_expression='旧讲法', ipa='old'))
        session.commit()
        yield session
    engine.dispose()


def args(db, user_id=7, role='user'):
    return dict(session=db, user=SimpleNamespace(id=user_id, role=role), filename='update.csv', content='standard_word,local_expression,ipa,notes\n吃饭,食饭,new,\n睡觉,,,\n'.encode(), location_payload={'location_name': '甲村', 'coordinates': '114,24', 'province': '', 't1': ''})


def test_upload_preserves_blank_metadata_and_updates_nonblank_fields(db):
    result = import_vocabulary_upload(**args(db), overwrite=True)
    location = db.query(Location).filter_by(user_id=7).one()
    assert location.coordinates == '114,24'
    assert [location.province, location.vocabulary_source, location.description, location.other, location.t1] == ['广东', '调查手稿', '说明', '其他', '55']
    assert result.imported_count == 1
    assert len(result.errors) == 1  # Partial replacement stays supported.


def test_explicit_nonblank_metadata_updates_are_kept(db):
    data = args(db)
    data['location_payload'].update(province='广西', t1='33')
    import_vocabulary_upload(**data, overwrite=True)
    location = db.query(Location).filter_by(user_id=7).one()
    assert (location.province, location.t1) == ('广西', '33')


def test_manager_previews_and_replaces_selected_owner_without_changing_ownership(db):
    data = args(db, user_id=1, role='admin')
    preview = preview_vocabulary_upload(**data, target_user_id=8)
    assert preview.would_delete_existing_count == 1
    assert db.query(Entry).filter_by(user_id=8, standard_word='旧词').count() == 1
    result = import_vocabulary_upload(**data, overwrite=True, target_user_id=8)
    assert result.deleted_existing_count == 1
    assert db.query(Entry).filter_by(user_id=8, standard_word='吃饭').count() == 1
    assert db.query(Entry).filter_by(user_id=7, standard_word='旧词').count() == 1
    assert db.query(Entry).filter_by(user_id=1).count() == 0
    assert db.query(Location).filter_by(user_id=8).one().province == '广东'
    log = db.query(VocabularyLog).one()
    assert log.user_id == 1
    assert 'user_id = 8' in log.target_scope
    assert json.loads(log.payload_json)['target_user_id'] == 8


@pytest.mark.parametrize('operation', [preview_vocabulary_upload, import_vocabulary_upload])
def test_self_scoped_users_cannot_target_another_owner(db, operation):
    with pytest.raises(HTTPException) as caught:
        operation(**args(db), target_user_id=8)
    assert caught.value.status_code == 403
    assert db.query(Entry).count() == 2


@pytest.mark.parametrize('operation', [preview_vocabulary_upload, import_vocabulary_upload])
def test_explicit_target_must_be_an_existing_location(db, operation):
    data = args(db, user_id=1, role='admin')
    with pytest.raises(HTTPException) as caught:
        operation(**data, target_user_id=99)
    assert caught.value.status_code == 404
    assert db.query(Location).count() == 2


def test_self_scoped_user_can_replace_explicit_own_location(db):
    result = import_vocabulary_upload(**args(db), overwrite=True, target_user_id=7)
    assert result.deleted_existing_count == 1
    assert db.query(Entry).filter_by(user_id=7, standard_word='吃饭').count() == 1


@pytest.mark.parametrize('preview', [True, False])
def test_routes_forward_explicit_target_owner(db, preview, monkeypatch):
    from app.routes import vocabulary as routes
    from app.routes.vocabulary import preview_vocabulary_upload_endpoint, upload_vocabulary
    async def no_cached_keys(pattern):
        return []
    monkeypatch.setattr(routes.redis_client, 'keys', no_cached_keys)
    data = args(db, user_id=1, role='admin')

    class Upload:
        filename = 'update.csv'
        async def read(self):
            return data['content']

    kwargs = dict(file=Upload(), location=json.dumps(data['location_payload']), parser_mode='table', fill_standard_from_local=False, current_user=data['user'], db=db, target_user_id=8)
    if not preview:
        kwargs['overwrite'] = True
    result = asyncio.run((preview_vocabulary_upload_endpoint if preview else upload_vocabulary)(**kwargs))
    assert (result.would_delete_existing_count if preview else result.deleted_existing_count) == 1
