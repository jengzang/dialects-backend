from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.custom.database import SessionLocal as SessionLocal_info
from app.custom.models import Information
from app.custom.write_submit import get_max_value
from app.schemas.admin import InformationBase
from app.schemas.user import CustomDataEdit, BatchDeleteRequest

router = APIRouter()


@router.get("/all")
async def get_all_own_custom_data(
    current_user: Optional[User] = Depends(get_current_user)
):
    """獲取用戶自己的所有 custom 數據"""
    if current_user is None:
        raise HTTPException(status_code=401, detail="請先登錄")

    session_info = SessionLocal_info()

    try:
        # 查詢用戶的所有 custom 數據
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
        # 單次批量提交限制：最多 50 條
        if len(infos) > 50:
            raise HTTPException(
                status_code=400,
                detail=f"❌ 單次批量提交最多 50 條數據（當前提交 {len(infos)} 條）"
            )

        # 速率限制（非管理員用戶）
        if current_user.role != "admin":
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)

            # 檢查用戶本小時的提交數量
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

            # 檢查用戶的總提交數量
            total_count = session_info.query(Information).filter(
                Information.user_id == current_user.id
            ).count()

            if total_count + len(infos) > 5000:
                remaining = 5000 - total_count
                raise HTTPException(
                    status_code=429,
                    detail=f"🚫 最多只能提交 5000 份資料（已提交 {total_count} 份，還可提交 {remaining} 份）"
                )

        # 創建記錄
        created_records = []
        base_time = datetime.utcnow()

        for i, info in enumerate(infos):
            # 驗證必填字段
            if not all([info.簡稱, info.音典分區, info.經緯度, info.特徵, info.值]):
                raise HTTPException(
                    status_code=400,
                    detail=f"第 {i+1} 條記錄缺少必填字段"
                )

            # 創建記錄
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
        # 查找記錄
        record = session_info.query(Information).filter(
            Information.user_id == current_user.id,
            Information.created_at == edit_request.created_at
        ).first()

        if not record:
            raise HTTPException(
                status_code=404,
                detail="記錄不存在或無權訪問"
            )

        # 更新允許的字段
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
        # 查找並刪除記錄
        deleted_records = session_info.query(Information).filter(
            Information.user_id == current_user.id,
            Information.created_at.in_(delete_request.created_at_list)
        ).all()

        if not deleted_records:
            raise HTTPException(
                status_code=404,
                detail="沒有找到匹配的記錄"
            )

        # 刪除記錄
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
