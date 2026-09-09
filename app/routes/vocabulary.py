from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.schemas.vocabulary import (
    VocabularyItemsResponse,
    VocabularyLocationOptionsResponse,
    VocabularyLocationResponse,
    VocabularyLocationsResponse,
    VocabularyLocationTransferRequest,
    VocabularyLocationTransferResponse,
    VocabularyLocationUpdateRequest,
    VocabularyLogResponse,
    VocabularyLogsResponse,
    VocabularyMapItemsResponse,
    VocabularyMapPointsResponse,
    VocabularyMeResponse,
    VocabularyPermissionResponse,
    VocabularyPermissionsResponse,
    VocabularyStandardWordsResponse,
    VocabularyPermissionUpdateRequest,
    VocabularyUploadPreviewResponse,
    VocabularyUploadResponse,
)
from app.service.auth.core.dependencies import get_current_admin_user, get_current_user
from app.service.auth.database.connection import SessionLocal as AuthSessionLocal
from app.service.auth.database.models import User
from app.service.vocabulary.database import get_db as get_vocabulary_db
from app.service.vocabulary.database import raise_vocabulary_database_busy_if_locked
from app.service.vocabulary.logging import record_vocabulary_log
from app.service.vocabulary.models import VocabularyEntry, VocabularyLocation, VocabularyLog, VocabularyPermission
from app.service.vocabulary.permissions import get_effective_permission_level, SELF_SCOPED_LEVELS
from app.service.vocabulary.query import (
    query_vocabulary_items,
    query_vocabulary_location_options,
    query_vocabulary_map_items,
    query_vocabulary_map_points,
    query_vocabulary_standard_words,
)
from app.service.vocabulary.service import import_vocabulary_upload
from app.service.vocabulary.service import preview_vocabulary_upload
from app.service.vocabulary.service import VocabularyImportConflictError
from app.redis_client import redis_client


router = APIRouter()


def _location_label(location: VocabularyLocation) -> str:
    parts = [
        location.province,
        location.city,
        location.county,
        location.town,
        location.administrative_village,
        location.natural_village,
    ]
    label = " · ".join(part for part in parts if part)
    return label or location.location_name


def _resolve_usernames(user_ids: set[int]) -> dict[int, str]:
    if not user_ids:
        return {}
    auth_db = AuthSessionLocal()
    try:
        rows = auth_db.query(User.id, User.username).filter(User.id.in_(user_ids)).all()
        return {row.id: row.username for row in rows}
    finally:
        auth_db.close()


def _resolve_user_reference(
    *,
    user_id: Optional[int],
    username: Optional[str],
    role_label: str,
) -> tuple[int, str]:
    cleaned_username = username.strip() if username is not None else None
    if user_id is None and not cleaned_username:
        raise HTTPException(status_code=400, detail=f"{role_label} 需要提供 user_id 或 username")

    auth_db = AuthSessionLocal()
    try:
        user_by_id = None
        user_by_name = None
        if user_id is not None:
            user_by_id = auth_db.query(User).filter(User.id == user_id).first()
            if user_by_id is None:
                raise HTTPException(status_code=404, detail=f"{role_label} user_id 不存在")
        if cleaned_username:
            user_by_name = auth_db.query(User).filter(User.username == cleaned_username).first()
            if user_by_name is None:
                raise HTTPException(status_code=404, detail=f"{role_label} username 不存在")
        if user_by_id is not None and user_by_name is not None and user_by_id.id != user_by_name.id:
            raise HTTPException(status_code=400, detail=f"{role_label} user_id 与 username 不匹配")
        resolved = user_by_id or user_by_name
        return resolved.id, resolved.username
    finally:
        auth_db.close()


def _location_response(location: VocabularyLocation, username: str = "") -> VocabularyLocationResponse:
    return VocabularyLocationResponse(
        user_id=location.user_id,
        username=username,
        location_name=location.location_name,
        coordinates=location.coordinates,
        province=location.province or "",
        city=location.city or "",
        county=location.county or "",
        town=location.town or "",
        administrative_village=location.administrative_village or "",
        natural_village=location.natural_village or "",
        yindian_region=location.yindian_region or "",
        atlas_region=location.atlas_region or "",
        location_label=_location_label(location),
    )


def _string_value(value: Any, *, allow_empty: bool = True) -> str:
    if value is None:
        cleaned = ""
    else:
        cleaned = str(value).strip()
    if not allow_empty and not cleaned:
        raise HTTPException(status_code=400, detail="coordinates 不能为空")
    return cleaned


def _log_response(log: VocabularyLog) -> VocabularyLogResponse:
    return VocabularyLogResponse(
        id=log.id,
        operation_id=log.operation_id,
        user_id=log.user_id,
        permission_level=log.permission_level,
        source=log.source,
        action=log.action,
        table_name=log.table_name,
        target_scope=log.target_scope or "",
        affected_rows=log.affected_rows,
        status=log.status,
        payload_json=log.payload_json or "{}",
        created_at=log.created_at.isoformat(sep=" ") if log.created_at else "",
    )


@router.get("/search/entries", response_model=VocabularyItemsResponse)
def get_vocabulary_items(
    q: Optional[str] = Query(default=None),
    search_fields: Optional[list[str]] = Query(default=None),
    locations: Optional[list[str]] = Query(default=None),
    province: Optional[str] = Query(default=None),
    city: Optional[str] = Query(default=None),
    standard_words: Optional[list[str]] = Query(default=None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_vocabulary_db),
):
    try:
        return query_vocabulary_items(
            session=db,
            q=q,
            search_fields=search_fields,
            locations=locations,
            province=province,
            city=city,
            standard_words=standard_words,
            page=page,
            page_size=page_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Vocabulary query failed: {exc}") from exc


@router.get("/search/map-points", response_model=VocabularyMapPointsResponse)
def get_vocabulary_map_points(
    q: Optional[str] = Query(default=None),
    search_fields: Optional[list[str]] = Query(default=None),
    locations: Optional[list[str]] = Query(default=None),
    province: Optional[str] = Query(default=None),
    city: Optional[str] = Query(default=None),
    db: Session = Depends(get_vocabulary_db),
):
    try:
        return query_vocabulary_map_points(
            session=db,
            q=q,
            search_fields=search_fields,
            locations=locations,
            province=province,
            city=city,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Vocabulary map query failed: {exc}") from exc


@router.get("/search/standard-words", response_model=VocabularyStandardWordsResponse)
def get_vocabulary_standard_words(
    q: Optional[str] = Query(default=None),
    search_fields: Optional[list[str]] = Query(default=None),
    locations: Optional[list[str]] = Query(default=None),
    province: Optional[str] = Query(default=None),
    city: Optional[str] = Query(default=None),
    limit: Optional[int] = Query(default=100, ge=1, le=10000),
    db: Session = Depends(get_vocabulary_db),
):
    try:
        return query_vocabulary_standard_words(
            session=db,
            q=q,
            search_fields=search_fields,
            locations=locations,
            province=province,
            city=city,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Vocabulary standard words query failed: {exc}") from exc


@router.get("/search/map-items", response_model=VocabularyMapItemsResponse)
def get_vocabulary_map_items(
    standard_words: list[str] = Query(...),
    q: Optional[str] = Query(default=None),
    search_fields: Optional[list[str]] = Query(default=None),
    locations: Optional[list[str]] = Query(default=None),
    province: Optional[str] = Query(default=None),
    city: Optional[str] = Query(default=None),
    db: Session = Depends(get_vocabulary_db),
):
    try:
        return query_vocabulary_map_items(
            session=db,
            standard_words=standard_words,
            q=q,
            search_fields=search_fields,
            locations=locations,
            province=province,
            city=city,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Vocabulary map items query failed: {exc}") from exc


@router.get("/search/location-options", response_model=VocabularyLocationOptionsResponse)
def get_vocabulary_location_options(
    db: Session = Depends(get_vocabulary_db),
):
    try:
        return query_vocabulary_location_options(session=db)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Vocabulary location options query failed: {exc}") from exc


@router.get("/locations", response_model=VocabularyLocationsResponse)
def get_vocabulary_locations(
    user_id: Optional[int] = Query(default=None),
    username: Optional[str] = Query(default=None),
    location_name: Optional[str] = Query(default=None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_vocabulary_db),
):
    permission_level = get_effective_permission_level(db, current_user)
    query = db.query(VocabularyLocation)

    if username is not None:
        auth_db = AuthSessionLocal()
        try:
            resolved_ids = [
                row.id for row in
                auth_db.query(User.id).filter(User.username == username).all()
            ]
        finally:
            auth_db.close()
        if not resolved_ids:
            return VocabularyLocationsResponse(locations=[], total=0, page=page, page_size=page_size)
        if user_id is not None and user_id not in resolved_ids:
            return VocabularyLocationsResponse(locations=[], total=0, page=page, page_size=page_size)
        if permission_level in SELF_SCOPED_LEVELS:
            if current_user.id not in resolved_ids:
                raise HTTPException(status_code=403, detail="只能读取自己的地点信息")
            query = query.filter(VocabularyLocation.user_id == current_user.id)
        else:
            query = query.filter(VocabularyLocation.user_id.in_(resolved_ids))
    elif permission_level in SELF_SCOPED_LEVELS:
        if user_id is not None and user_id != current_user.id:
            raise HTTPException(status_code=403, detail="只能读取自己的地点信息")
        query = query.filter(VocabularyLocation.user_id == current_user.id)
    elif user_id is not None:
        query = query.filter(VocabularyLocation.user_id == user_id)

    if location_name:
        query = query.filter(VocabularyLocation.location_name == location_name)

    total = query.count()
    rows = (
        query.order_by(
            VocabularyLocation.user_id.asc(),
            VocabularyLocation.location_name.asc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    usernames = _resolve_usernames({row.user_id for row in rows})

    return VocabularyLocationsResponse(
        locations=[_location_response(row, usernames.get(row.user_id, "")) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.patch("/locations/{location_name}", response_model=VocabularyLocationResponse)
def update_vocabulary_location(
    location_name: str,
    params: VocabularyLocationUpdateRequest,
    user_id: Optional[int] = Query(default=None),
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_vocabulary_db),
):
    permission_level = get_effective_permission_level(db, current_user)
    raw_updates = params.model_dump(exclude_unset=True)
    if not raw_updates:
        raise HTTPException(status_code=400, detail="至少需要提供一个可更新字段")

    updates: dict[str, str] = {}
    for field, value in raw_updates.items():
        updates[field] = _string_value(value, allow_empty=field != "coordinates")

    query = db.query(VocabularyLocation).filter(
        VocabularyLocation.location_name == location_name,
    )
    if permission_level in SELF_SCOPED_LEVELS:
        if user_id is not None and user_id != current_user.id:
            raise HTTPException(status_code=403, detail="只能编辑自己的地点信息")
        query = query.filter(VocabularyLocation.user_id == current_user.id)
    elif user_id is not None:
        query = query.filter(VocabularyLocation.user_id == user_id)

    matches = query.order_by(VocabularyLocation.user_id.asc()).all()
    if not matches:
        raise HTTPException(status_code=404, detail="未找到地点信息")
    if permission_level == "manage" and user_id is None and len(matches) > 1:
        raise HTTPException(status_code=400, detail="同名地点属于多个用户，请通过 user_id 指定目标")

    target = matches[0]
    changes = {}
    for field, value in updates.items():
        old_value = getattr(target, field) or ""
        if old_value != value:
            changes[field] = {"old": old_value, "new": value}
        setattr(target, field, value)

    try:
        record_vocabulary_log(
            session=db,
            user_id=current_user.id,
            permission_level=permission_level,
            source="location_editor",
            action="update_location",
            table_name="vocabulary_locations",
            target_scope=f"user_id = {target.user_id}; location_name = {location_name}",
            affected_rows=1,
            payload={
                "location_name": location_name,
                "target_user_id": target.user_id,
                "updated_fields": sorted(updates),
                "changes": changes,
            },
        )
        db.commit()
        db.refresh(target)
    except Exception as exc:
        db.rollback()
        raise_vocabulary_database_busy_if_locked(exc)
        raise

    usernames = _resolve_usernames({target.user_id})
    return _location_response(target, usernames.get(target.user_id, ""))


@router.post("/locations/transfer", response_model=VocabularyLocationTransferResponse)
def transfer_vocabulary_location(
    params: VocabularyLocationTransferRequest,
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_vocabulary_db),
):
    permission_level = get_effective_permission_level(db, current_user)
    if permission_level != "manage":
        raise HTTPException(status_code=403, detail="仅 manage 可转移地点权限")

    location_name = _string_value(params.location_name)
    if not location_name:
        raise HTTPException(status_code=400, detail="location_name 不能为空")

    source_user_id, source_username = _resolve_user_reference(
        user_id=params.user_id,
        username=params.username,
        role_label="源用户",
    )
    target_user_id, target_username = _resolve_user_reference(
        user_id=params.target_user_id,
        username=params.target_username,
        role_label="目标用户",
    )
    if source_user_id == target_user_id:
        raise HTTPException(status_code=400, detail="源用户和目标用户不能相同")

    target_exists = db.query(VocabularyLocation).filter(
        VocabularyLocation.user_id == target_user_id,
        VocabularyLocation.location_name == location_name,
    ).first()
    if target_exists is not None:
        raise HTTPException(status_code=409, detail="目标用户已有同名地点，不能转移")

    target = db.query(VocabularyLocation).filter(
        VocabularyLocation.user_id == source_user_id,
        VocabularyLocation.location_name == location_name,
    ).first()
    if target is None:
        raise HTTPException(status_code=404, detail="未找到地点信息")

    entry_query = db.query(VocabularyEntry).filter(
        VocabularyEntry.user_id == source_user_id,
        VocabularyEntry.location_name == location_name,
    )
    transferred_entries_count = entry_query.count()

    try:
        target.user_id = target_user_id
        entry_query.update(
            {VocabularyEntry.user_id: target_user_id},
            synchronize_session=False,
        )
        record_vocabulary_log(
            session=db,
            user_id=current_user.id,
            permission_level=permission_level,
            source="location_editor",
            action="transfer_location",
            table_name="vocabulary_locations",
            target_scope=(
                f"source_user_id = {source_user_id}; "
                f"target_user_id = {target_user_id}; "
                f"location_name = {location_name}"
            ),
            affected_rows=1 + transferred_entries_count,
            payload={
                "location_name": location_name,
                "source_user_id": source_user_id,
                "source_username": source_username,
                "target_user_id": target_user_id,
                "target_username": target_username,
                "transferred_entries_count": transferred_entries_count,
                "rollback_supported": True,
            },
        )
        db.commit()
        db.refresh(target)
    except Exception as exc:
        db.rollback()
        raise_vocabulary_database_busy_if_locked(exc)
        raise

    return VocabularyLocationTransferResponse(
        success=True,
        location_name=target.location_name,
        permission_level=permission_level,
        source_user_id=source_user_id,
        source_username=source_username,
        target_user_id=target_user_id,
        target_username=target_username,
        transferred_entries_count=transferred_entries_count,
    )


@router.delete("/locations/{location_name}")
def delete_vocabulary_location(
    location_name: str,
    user_id: Optional[int] = Query(default=None),
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_vocabulary_db),
):
    permission_level = get_effective_permission_level(db, current_user)
    if permission_level not in ("manage", "admin"):
        raise HTTPException(status_code=403, detail="仅 manage/admin 可删除地点")

    query = db.query(VocabularyLocation).filter(
        VocabularyLocation.location_name == location_name,
    )
    if user_id is not None:
        query = query.filter(VocabularyLocation.user_id == user_id)

    targets = query.all()
    if not targets:
        raise HTTPException(status_code=404, detail="未找到地点信息")
    if user_id is None and len(targets) > 1:
        raise HTTPException(
            status_code=400,
            detail="同名地点属于多个用户，请通过 user_id 参数指定目标",
        )

    target = targets[0]
    entry_count = db.query(VocabularyEntry).filter(
        VocabularyEntry.user_id == target.user_id,
        VocabularyEntry.location_name == target.location_name,
    ).count()

    try:
        db.query(VocabularyEntry).filter(
            VocabularyEntry.user_id == target.user_id,
            VocabularyEntry.location_name == target.location_name,
        ).delete(synchronize_session=False)
        db.delete(target)
        record_vocabulary_log(
            session=db,
            user_id=current_user.id,
            permission_level=permission_level,
            source="location_editor",
            action="delete_location",
            table_name="vocabulary_locations",
            target_scope=f"user_id = {target.user_id}; location_name = {location_name}",
            affected_rows=1 + entry_count,
            payload={
                "location_name": location_name,
                "target_user_id": target.user_id,
                "deleted_entries_count": entry_count,
            },
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        raise_vocabulary_database_busy_if_locked(exc)
        raise

    return {"status": "deleted", "location_name": location_name, "deleted_entries": entry_count}


@router.get("/logs", response_model=VocabularyLogsResponse)
def get_vocabulary_logs(
    user_id: Optional[int] = Query(default=None),
    permission_level: Optional[str] = Query(default=None),
    source: Optional[str] = Query(default=None),
    action: Optional[str] = Query(default=None),
    table_name: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_vocabulary_db),
):
    effective_permission = get_effective_permission_level(db, current_user)
    if effective_permission != "manage":
        raise HTTPException(status_code=403, detail="只有 manage 用户可以查看词表编辑日志")

    query = db.query(VocabularyLog)
    if getattr(current_user, "role", None) != "admin":
        query = query.filter(VocabularyLog.action != "set_permission")
    if user_id is not None:
        query = query.filter(VocabularyLog.user_id == user_id)
    if permission_level:
        query = query.filter(VocabularyLog.permission_level == permission_level)
    if source:
        query = query.filter(VocabularyLog.source == source)
    if action:
        query = query.filter(VocabularyLog.action == action)
    if table_name:
        query = query.filter(VocabularyLog.table_name == table_name)
    if status:
        query = query.filter(VocabularyLog.status == status)

    total = query.count()
    rows = (
        query.order_by(VocabularyLog.created_at.desc(), VocabularyLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return VocabularyLogsResponse(
        logs=[_log_response(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/imports", response_model=VocabularyUploadResponse)
async def upload_vocabulary(
    file: UploadFile = File(...),
    location: str = Form(...),
    parser_mode: str = Form("auto"),
    overwrite: bool = Form(False),
    fill_standard_from_local: bool = Form(False),
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_vocabulary_db),
):
    content = await file.read()
    try:
        result = import_vocabulary_upload(
            session=db,
            user=current_user,
            filename=file.filename or "upload",
            content=content,
            location_payload=location,
            parser_mode=parser_mode,
            overwrite=overwrite,
            fill_standard_from_local=fill_standard_from_local,
        )
        try:
            keys = await redis_client.keys("vocab_sql_count:vocabulary_entries*")
            if keys:
                await redis_client.delete(*keys)
        except Exception:
            pass
        return result
    except HTTPException:
        raise
    except VocabularyImportConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise_vocabulary_database_busy_if_locked(exc)
        raise HTTPException(status_code=500, detail=f"Vocabulary upload failed: {exc}")


@router.post("/imports/preview", response_model=VocabularyUploadPreviewResponse)
async def preview_vocabulary_upload_endpoint(
    file: UploadFile = File(...),
    location: str = Form(...),
    parser_mode: str = Form("auto"),
    fill_standard_from_local: bool = Form(False),
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_vocabulary_db),
):
    content = await file.read()
    try:
        return preview_vocabulary_upload(
            session=db,
            user=current_user,
            filename=file.filename or "upload",
            content=content,
            location_payload=location,
            parser_mode=parser_mode,
            fill_standard_from_local=fill_standard_from_local,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise_vocabulary_database_busy_if_locked(exc)
        raise HTTPException(status_code=500, detail=f"Vocabulary upload preview failed: {exc}")


@router.get("/me", response_model=VocabularyMeResponse)
def get_my_vocabulary_context(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_vocabulary_db),
):
    if current_user.role == "admin":
        return VocabularyMeResponse(
            user_id=current_user.id,
            permission_level="manage",
            can_upload=True,
            can_manage_entries=True,
            can_view_logs=True,
        )

    permission = db.query(VocabularyPermission).filter(
        VocabularyPermission.user_id == current_user.id
    ).first()
    permission_level = permission.permission_level if permission is not None else None
    return VocabularyMeResponse(
        user_id=current_user.id,
        permission_level=permission_level,
        can_upload=permission_level in SELF_SCOPED_LEVELS or permission_level == "manage",
        can_manage_entries=permission_level == "manage",
        can_view_logs=permission_level == "manage",
    )


@router.get("/admin/permissions", response_model=VocabularyPermissionsResponse)
def get_vocabulary_permissions(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_vocabulary_db),
):
    query = db.query(VocabularyPermission)
    total = query.count()
    rows = (
        query.order_by(VocabularyPermission.user_id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return VocabularyPermissionsResponse(
        permissions=[
            VocabularyPermissionResponse(
                user_id=row.user_id,
                permission_level=row.permission_level,
            )
            for row in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/admin/permissions/{user_id}", response_model=VocabularyPermissionResponse)
def get_vocabulary_permission(
    user_id: int,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_vocabulary_db),
):
    permission = db.query(VocabularyPermission).filter(
        VocabularyPermission.user_id == user_id
    ).first()
    return VocabularyPermissionResponse(
        user_id=user_id,
        permission_level=permission.permission_level if permission is not None else None,
    )


@router.put("/admin/permissions/{user_id}", response_model=VocabularyPermissionResponse)
def set_vocabulary_permission(
    user_id: int,
    params: VocabularyPermissionUpdateRequest,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_vocabulary_db),
):
    try:
        previous_permission = db.query(VocabularyPermission).filter(
            VocabularyPermission.user_id == user_id
        ).first()
        before = (
            {"permission_level": previous_permission.permission_level}
            if previous_permission is not None
            else None
        )
        if params.permission_level == "none":
            affected_rows = 0
            if previous_permission is not None:
                db.delete(previous_permission)
                affected_rows = 1
            record_vocabulary_log(
                session=db,
                user_id=current_admin.id,
                permission_level="manage",
                source="admin",
                action="set_permission",
                table_name="vocabulary_permissions",
                target_scope=f"target_user_id = {user_id}",
                affected_rows=affected_rows,
                payload={
                    "target_user_id": user_id,
                    "permission_level": None,
                    "before": before,
                    "after": None,
                    "rollback_supported": before is not None,
                },
            )
            db.commit()
            return VocabularyPermissionResponse(
                user_id=user_id,
                permission_level=None,
            )

        statement = sqlite_insert(VocabularyPermission).values(
            user_id=user_id,
            permission_level=params.permission_level,
        )
        db.execute(
            statement.on_conflict_do_update(
                index_elements=["user_id"],
                set_={"permission_level": statement.excluded.permission_level},
            )
        )
        db.flush()
        permission = db.query(VocabularyPermission).filter(
            VocabularyPermission.user_id == user_id
        ).one()

        record_vocabulary_log(
            session=db,
            user_id=current_admin.id,
            permission_level="manage",
            source="admin",
            action="set_permission",
            table_name="vocabulary_permissions",
            target_scope=f"target_user_id = {user_id}",
            affected_rows=1,
            payload={
                "target_user_id": user_id,
                "permission_level": params.permission_level,
                "before": before,
                "after": {"permission_level": params.permission_level},
                "rollback_supported": True,
            },
        )
        db.commit()
        db.refresh(permission)
    except Exception as exc:
        db.rollback()
        raise_vocabulary_database_busy_if_locked(exc)
        raise
    return VocabularyPermissionResponse(
        user_id=permission.user_id,
        permission_level=permission.permission_level,
    )
