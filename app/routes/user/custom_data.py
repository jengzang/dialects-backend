from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy import func, distinct, or_

from app.service.auth.core.dependencies import get_current_user
from app.service.auth.database.models import User
from app.service.user.core.database import SessionLocal as SessionLocal_info
from app.service.user.core.models import Information, UserRegion
from app.service.user.submission.submit import get_max_value
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

router = APIRouter()


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


def list_records_by_point_for_user(user: User, location: str, region: str) -> List[dict]:
    session_info = SessionLocal_info()
    try:
        rows = session_info.query(Information).filter(
            Information.user_id == user.id,
            Information.簡稱 == location,
            Information.音典分區 == region,
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
        rows = session_info.query(Information).filter(
            Information.user_id == user.id,
            Information.特徵 == feature,
            Information.聲韻調 == phonology,
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
    location: str = Query(..., description="方言點簡稱"),
    region: str = Query(..., description="音典分區"),
    current_user: Optional[User] = Depends(get_current_user),
):
    user = _require_current_user(current_user)
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
async def batch_create_custom_data(
    infos: List[InformationBase],
    current_user: Optional[User] = Depends(get_current_user)
):
    """批量創建 custom 數據"""
    if current_user is None:
        raise HTTPException(status_code=401, detail="請先登錄")

    session_info = SessionLocal_info()

    try:
        if len(infos) > 50:
            raise HTTPException(
                status_code=400,
                detail=f"❌ 單次批量提交最多 50 條數據（當前提交 {len(infos)} 條）"
            )

        if current_user.role != "admin":
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)

            count_last_hour = session_info.query(Information).filter(
                Information.user_id == current_user.id,
                Information.created_at >= one_hour_ago
            ).count()

            if count_last_hour + len(infos) > 500:
                remaining = 500 - count_last_hour
                raise HTTPException(
                    status_code=429,
                    detail=f"💥 每小時最多提交 500 份資料（本小時已提交 {count_last_hour} 份，還可提交 {remaining} 份）"
                )

            total_count = session_info.query(Information).filter(
                Information.user_id == current_user.id
            ).count()

            if total_count + len(infos) > 5000:
                remaining = 5000 - total_count
                raise HTTPException(
                    status_code=429,
                    detail=f"🚫 最多只能提交 5000 份資料（已提交 {total_count} 份，還可提交 {remaining} 份）"
                )

        created_records = []
        base_time = datetime.utcnow()

        for i, info in enumerate(infos):
            if not all([info.簡稱, info.音典分區, info.經緯度, info.特徵, info.值]):
                raise HTTPException(
                    status_code=400,
                    detail=f"第 {i+1} 條記錄缺少必填字段"
                )

            record = Information(
                user_id=current_user.id,
                username=current_user.username,
                簡稱=info.簡稱,
                音典分區=info.音典分區,
                經緯度=info.經緯度,
                聲韻調=info.聲韻調,
                特徵=info.特徵,
                值=info.值,
                說明=info.說明,
                created_at=base_time + timedelta(milliseconds=i*50),
                maxValue=get_max_value(info.值)
            )
            session_info.add(record)
            created_records.append(record)

        session_info.commit()

        return {
            "message": f"成功創建 {len(created_records)} 條記錄",
            "data": created_records
        }
    except HTTPException:
        raise
    except Exception as e:
        session_info.rollback()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
    finally:
        session_info.close()


@router.put("/edit")
async def edit_custom_data(
    edit_request: CustomDataEdit,
    current_user: Optional[User] = Depends(get_current_user)
):
    """編輯已有的 custom 數據"""
    if current_user is None:
        raise HTTPException(status_code=401, detail="請先登錄")

    session_info = SessionLocal_info()

    try:
        record = session_info.query(Information).filter(
            Information.user_id == current_user.id,
            Information.created_at == edit_request.created_at
        ).first()

        if not record:
            raise HTTPException(
                status_code=404,
                detail="記錄不存在或無權訪問"
            )

        if edit_request.簡稱 is not None:
            record.簡稱 = edit_request.簡稱
        if edit_request.音典分區 is not None:
            record.音典分區 = edit_request.音典分區
        if edit_request.經緯度 is not None:
            record.經緯度 = edit_request.經緯度
        if edit_request.聲韻調 is not None:
            record.聲韻調 = edit_request.聲韻調
        if edit_request.特徵 is not None:
            record.特徵 = edit_request.特徵
        if edit_request.值 is not None:
            record.值 = edit_request.值
            record.maxValue = get_max_value(edit_request.值)
        if edit_request.說明 is not None:
            record.說明 = edit_request.說明

        session_info.commit()
        session_info.refresh(record)

        return {
            "message": "更新成功",
            "data": record
        }
    except HTTPException:
        raise
    except Exception as e:
        session_info.rollback()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
    finally:
        session_info.close()


@router.delete("/batch-delete")
async def batch_delete_custom_data(
    delete_request: BatchDeleteRequest,
    current_user: Optional[User] = Depends(get_current_user)
):
    """批量刪除 custom 數據"""
    if current_user is None:
        raise HTTPException(status_code=401, detail="請先登錄")

    session_info = SessionLocal_info()

    try:
        deleted_records = session_info.query(Information).filter(
            Information.user_id == current_user.id,
            Information.created_at.in_(delete_request.created_at_list)
        ).all()

        if not deleted_records:
            raise HTTPException(
                status_code=404,
                detail="沒有找到匹配的記錄"
            )

        for record in deleted_records:
            session_info.delete(record)

        session_info.commit()

        return {
            "message": f"成功刪除 {len(deleted_records)} 條記錄",
            "deleted_count": len(deleted_records),
            "deleted_records": deleted_records
        }
    except HTTPException:
        raise
    except Exception as e:
        session_info.rollback()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
    finally:
        session_info.close()
