from typing import List

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func

from app.auth.models import User
from app.custom.database import SessionLocal as SessionLocal_info
from app.auth.database import SessionLocal as SessionLocal_user
from app.custom.models import Information
from app.schemas.admin import InformationBase

router = APIRouter()


@router.get("/all", response_model=List[InformationBase])
async def get_informations():
    # 使用兩個不同的 session
    session_info = SessionLocal_info()
    session_user = SessionLocal_user()

    try:
        informations = session_info.query(Information).all()
        result = []

        # 遍歷資料，根據 user_id 查找對應的 username
        for info in informations:
            user = session_user.query(User).filter(User.id == info.user_id).first()
            if user:
                result.append({
                    "簡稱": info.簡稱,
                    "音典分區": info.音典分區,
                    "經緯度": info.經緯度,
                    "聲韻調": info.聲韻調,
                    "特徵": info.特徵,
                    "值": info.值,
                    "說明": info.說明,
                    "username": user.username,  # 加上對應的用戶名稱
                    "created_at": info.created_at,
                })
            else:
                result.append({
                    "id": info.id,
                    "error": "未找到對應的用戶"
                })

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
    finally:
        # 關閉 session
        session_info.close()
        session_user.close()

# 新的 API 路由：/num，用於返回每個用戶的數據數量
@router.get("/num")
async def get_user_data_count():
    session_info = SessionLocal_info()
    session_user = SessionLocal_user()

    try:
        # 查詢每個 user 的數據數量
        user_data_count = session_info.query(
            Information.user_id, func.count(Information.id).label('data_count')
        ).group_by(Information.user_id).all()

        result = []

        # 根據 user_id 查找對應的 username 並組裝結果
        for user_id, data_count in user_data_count:
            user = session_user.query(User).filter(User.id == user_id).first()
            if user:
                result.append({
                    "username": user.username,
                    "data_count": data_count  # 返回用戶的數據數量
                })
            else:
                result.append({
                    "user_id": user_id,
                    "error": "未找到對應的用戶"
                })

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
    finally:
        session_info.close()
        session_user.close()

# 根據用戶名查詢用戶數據
@router.get("/user", response_model=List[InformationBase])
async def get_custom_peruser(query: str = Query(..., description="用戶名")):
    session_info = SessionLocal_info()
    session_user = SessionLocal_user()

    try:
        # 根據用戶名查找 User
        user = session_user.query(User).filter(User.username == query).first()
        if not user:
            raise HTTPException(status_code=404, detail="用戶未找到")

        # 根據用戶 ID 查找該用戶的所有數據
        user_data = session_info.query(Information).filter(Information.user_id == user.id).all()

        if not user_data:
            return []  # 如果該用戶沒有數據，返回空列表

        # 直接返回符合 InformationBase 結構的數據
        return user_data

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
    finally:
        session_info.close()
        session_user.close()