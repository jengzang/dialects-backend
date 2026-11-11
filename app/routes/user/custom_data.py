from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy import func, distinct, or_

from app.service.auth.core.dependencies import get_current_user
from app.service.auth.database.models import User
from app.service.user.core.database import SessionLocal as SessionLocal_info
from app.service.user.core.models import Information, UserRegion
from app.service.user.submission.get_custom import _expand_phonology_list
from app.schemas.admin.submissions import InformationBase

from app.schemas.user import (
    CustomDataEdit,
    BatchDeleteRequest,
    CustomFeatureGroupListResponse,
    CustomFeatureGroupResponse,
    CustomPointGroupListResponse,
    CustomPointGroupResponse,
    CustomDataListResponse,
    CustomDataRecord,
    CustomDataAllResponse,
)

from app.routes.user.custom_mutation_limits import LimitedMutationRoute
from app.schemas.user.custom_mutations import BatchUpdateRequest, BatchDeleteByIdRequest, SaveCustomDataRequest
from app.service.user.submission import mutations, legacy_mutations

router = APIRouter(route_class=LimitedMutationRoute)


def _require_current_user(current_user: Optional[User]) -> User:
    if current_user is None:
        raise HTTPException(status_code=401, detail="請先登錄")
    return current_user


def list_user_custom_counts(user: User) -> dict:
    session_info = SessionLocal_info()
    try:
        custom_region_total = session_info.query(UserRegion.id).filter(
            UserRegion.user_id == user.id
        ).count()
        custom_data_total = session_info.query(Information.id).filter(
            Information.user_id == user.id
        ).count()
        return {
            "success": True,
            "custom_region_total": custom_region_total,
            "custom_data_total": custom_data_total,
        }
    finally:
        session_info.close()


def list_grouped_points_for_user(user: User, keyword: Optional[str] = None) -> dict:
    session_info = SessionLocal_info()
    try:
        query = session_info.query(
            Information.簡稱.label("簡稱"),
            Information.音典分區.label("音典分區"),
            func.min(Information.經緯度).label("經緯度"),
            func.count(Information.id).label("feature_count"),
            func.max(Information.created_at).label("updated_at"),
        ).filter(
            Information.user_id == user.id
        )

        if keyword:
            like_value = f"%{keyword.strip()}%"
            query = query.filter(
                or_(
                    Information.簡稱.like(like_value),
                    Information.音典分區.like(like_value),
                )
            )

        rows = query.group_by(
            Information.簡稱,
            Information.音典分區,
        ).order_by(
            func.max(Information.created_at).desc(),
            Information.簡稱.asc(),
            Information.音典分區.asc(),
        ).all()

        data = [
            CustomPointGroupResponse(
                point_key=f"{row.簡稱}||{row.音典分區}",
                簡稱=row.簡稱,
                音典分區=row.音典分區,
                經緯度=row.經緯度,
                feature_count=row.feature_count,
                updated_at=row.updated_at,
            )
            for row in rows
        ]
        return CustomPointGroupListResponse(success=True, data=data, total=len(data)).model_dump()
    finally:
        session_info.close()


def list_grouped_features_for_user(user: User, keyword: Optional[str] = None) -> dict:
    session_info = SessionLocal_info()
    try:
        query = session_info.query(
            Information.特徵.label("特徵"),
            Information.聲韻調.label("聲韻調"),
            func.count(distinct((Information.簡稱 + "||" + Information.音典分區))).label("location_count"),
            func.max(Information.created_at).label("updated_at"),
        ).filter(
            Information.user_id == user.id
        )

        if keyword:
            like_value = f"%{keyword.strip()}%"
            query = query.filter(
                or_(
                    Information.特徵.like(like_value),
                    Information.聲韻調.like(like_value),
                )
            )

        rows = query.group_by(
            Information.特徵,
            Information.聲韻調,
        ).order_by(
            func.max(Information.created_at).desc(),
            Information.特徵.asc(),
            Information.聲韻調.asc(),
        ).all()

        data = [
            CustomFeatureGroupResponse(
                feature_key=f"{row.特徵}||{row.聲韻調}",
                特徵=row.特徵,
                聲韻調=row.聲韻調,
                location_count=row.location_count,
                updated_at=row.updated_at,
            )
            for row in rows
        ]
        return CustomFeatureGroupListResponse(success=True, data=data, total=len(data)).model_dump()
    finally:
        session_info.close()


def list_records_by_point_for_user(user: User, location: Optional[str] = None, region: Optional[str] = None) -> List[dict]:
    session_info = SessionLocal_info()
    try:
        filters = [Information.user_id == user.id]
        if location:
            filters.append(Information.簡稱 == location)
        if region:
            filters.append(Information.音典分區 == region)

        rows = session_info.query(Information).filter(
            *filters
        ).order_by(
            Information.created_at.asc(),
            Information.id.asc(),
        ).all()
        return [CustomDataRecord.model_validate(row, from_attributes=True).model_dump() for row in rows]
    finally:
        session_info.close()


def list_records_by_feature_for_user(user: User, feature: str, phonology: str) -> List[dict]:
    session_info = SessionLocal_info()
    try:
        phonology_candidates = _expand_phonology_list([phonology]) if phonology else [phonology]
        rows = session_info.query(Information).filter(
            Information.user_id == user.id,
            Information.特徵 == feature,
            Information.聲韻調.in_(phonology_candidates),
        ).order_by(
            Information.created_at.asc(),
            Information.id.asc(),
            Information.簡稱.asc(),
            Information.音典分區.asc(),
        ).all()
        return [CustomDataRecord.model_validate(row, from_attributes=True).model_dump() for row in rows]
    finally:
        session_info.close()


@router.get("/all", response_model=CustomDataAllResponse)
async def get_all_own_custom_data(
    current_user: Optional[User] = Depends(get_current_user)
):
    """獲取用戶自己的所有 custom 數據"""
    if current_user is None:
        raise HTTPException(status_code=401, detail="請先登錄")

    session_info = SessionLocal_info()

    try:
        custom_data = session_info.query(Information).filter(
            Information.user_id == current_user.id
        ).order_by(Information.created_at.desc()).all()

        return {
            "username": current_user.username,
            "total": len(custom_data),
            "data": custom_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
    finally:
        session_info.close()


@router.get("/counts")
async def get_user_custom_counts(
    current_user: Optional[User] = Depends(get_current_user),
):
    user = _require_current_user(current_user)
    return list_user_custom_counts(user)


@router.get("/points", response_model=CustomPointGroupListResponse)
async def get_user_custom_points(
    keyword: Optional[str] = Query(None, description="可選關鍵詞模糊搜索"),
    current_user: Optional[User] = Depends(get_current_user),
):
    user = _require_current_user(current_user)
    return list_grouped_points_for_user(user, keyword)


@router.get("/features", response_model=CustomFeatureGroupListResponse)
async def get_user_custom_feature_groups(
    keyword: Optional[str] = Query(None, description="可選關鍵詞模糊搜索"),
    current_user: Optional[User] = Depends(get_current_user),
):
    user = _require_current_user(current_user)
    return list_grouped_features_for_user(user, keyword)


@router.get("/data-by-point", response_model=CustomDataListResponse)
async def get_custom_data_by_point(
    location: Optional[str] = Query(None, description="方言點簡稱"),
    region: Optional[str] = Query(None, description="音典分區"),
    current_user: Optional[User] = Depends(get_current_user),
):
    user = _require_current_user(current_user)
    if not location and not region:
        raise HTTPException(status_code=400, detail="必须提供地点或分区参数之一")
    return {"success": True, "data": list_records_by_point_for_user(user, location, region)}


@router.get("/data-by-feature", response_model=CustomDataListResponse)
async def get_custom_data_by_feature(
    feature: str = Query(..., description="特徵名稱"),
    phonology: str = Query(..., description="聲韻調類別"),
    current_user: Optional[User] = Depends(get_current_user),
):
    user = _require_current_user(current_user)
    return {"success": True, "data": list_records_by_feature_for_user(user, feature, phonology)}


@router.post("/batch-create")
def batch_create_custom_data(infos: List[InformationBase], current_user: Optional[User] = Depends(get_current_user)):
    return legacy_mutations.create_legacy(_require_current_user(current_user), infos, SessionLocal_info)


@router.put("/edit")
def edit_custom_data(edit_request: CustomDataEdit, current_user: Optional[User] = Depends(get_current_user)):
    return legacy_mutations.edit_legacy(_require_current_user(current_user), edit_request, SessionLocal_info)


@router.delete("/batch-delete")
def batch_delete_custom_data(delete_request: BatchDeleteRequest, current_user: Optional[User] = Depends(get_current_user)):
    return legacy_mutations.delete_legacy(_require_current_user(current_user), delete_request.created_at_list, SessionLocal_info)


@router.put("/batch-update")
def batch_update_custom_data(request: BatchUpdateRequest, current_user: Optional[User] = Depends(get_current_user)):
    return mutations.batch_update(_require_current_user(current_user), request, SessionLocal_info)


@router.delete("/batch-delete-by-id")
def batch_delete_custom_data_by_id(request: BatchDeleteByIdRequest, current_user: Optional[User] = Depends(get_current_user)):
    return mutations.batch_delete_by_id(_require_current_user(current_user), request, SessionLocal_info)


@router.post("/save")
def save_custom_data(request: SaveCustomDataRequest, current_user: Optional[User] = Depends(get_current_user)):
    return mutations.save_custom_data(_require_current_user(current_user), request, SessionLocal_info)
