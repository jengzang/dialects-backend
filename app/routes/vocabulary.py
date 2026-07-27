from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.schemas.vocabulary import (
    VocabularyItemsResponse,
    VocabularyLocationOptionsResponse,
    VocabularyLocationResponse,
    VocabularyLocationsResponse,
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
from app.service.auth.database.models import User
from app.service.vocabulary.database import get_db as get_vocabulary_db
from app.service.vocabulary.database import raise_vocabulary_database_busy_if_locked
from app.service.vocabulary.logging import record_vocabulary_log
from app.service.vocabulary.models import VocabularyLocation, VocabularyLog, VocabularyPermission
from app.service.vocabulary.permissions import get_effective_permission_level
from app.service.vocabulary.query import (
    query_vocabulary_items,
    query_vocabulary_location_options,
    query_vocabulary_map_items,
    query_vocabulary_map_points,
    query_vocabulary_standard_words,
)
from app.service.vocabulary.service import import_vocabulary_upload
from app.service.vocabulary.service import preview_vocabulary_upload


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
    label = " / ".join(part for part in parts if part)
    return label or location.location_name


def _location_response(location: VocabularyLocation) -> VocabularyLocationResponse:
    return VocabularyLocationResponse(
        user_id=location.user_id,
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
    db: Session = Depends(get_vocabulary_db),
):
    try:
        return query_vocabulary_map_points(
            session=db,
            q=q,
            search_fields=search_fields,
            locations=locations,
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
    limit: Optional[int] = Query(default=None, ge=1),
    db: Session = Depends(get_vocabulary_db),
):
    try:
        return query_vocabulary_standard_words(
            session=db,
            q=q,
            search_fields=search_fields,
            locations=locations,
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
    db: Session = Depends(get_vocabulary_db),
):
    try:
        return query_vocabulary_map_items(
            session=db,
            standard_words=standard_words,
            q=q,
            search_fields=search_fields,
            locations=locations,
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
    location_name: Optional[str] = Query(default=None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_vocabulary_db),
):
    permission_level = get_effective_permission_level(db, current_user)
    query = db.query(VocabularyLocation)

    if permission_level == "edit":
        if user_id is not None and user_id != current_user.id:
            raise HTTPException(status_code=403, detail="edit 用户只能读取自己的地点信息")
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

    return VocabularyLocationsResponse(
        locations=[_location_response(row) for row in rows],
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
    if permission_level == "edit":
        if user_id is not None and user_id != current_user.id:
            raise HTTPException(status_code=403, detail="edit 用户只能编辑自己的地点信息")
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

    return _location_response(target)


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
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_vocabulary_db),
):
    content = await file.read()
    try:
        return import_vocabulary_upload(
            session=db,
            user=current_user,
            filename=file.filename or "upload",
            content=content,
            location_payload=location,
            parser_mode=parser_mode,
            overwrite=overwrite,
        )
    except HTTPException:
        raise
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
        can_upload=permission_level in {"edit", "manage"},
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
            if previous_permission is not None:
                db.delete(previous_permission)
                db.commit()
            return VocabularyPermissionResponse(
                user_id=user_id,
                permission_level=None,
            )

        permission = db.query(VocabularyPermission).filter(
            VocabularyPermission.user_id == user_id
        ).first()
        if permission is not None:
            permission.permission_level = params.permission_level
        else:
            permission = VocabularyPermission(user_id=user_id, permission_level=params.permission_level)
            db.add(permission)
        db.flush()

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
