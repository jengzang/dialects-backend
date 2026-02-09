# routes/form_submit.py
"""
[PKG] 路由模塊：處理 /api/submit_form 提交用戶填寫的語音資料。
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.custom.database import get_db as get_db_custom
from app.custom.delete import handle_form_deletion
from app.schemas import FormData
from app.custom.write_submit import handle_form_submission
from app.logs.service.api_limiter import ApiLimiter
from app.auth.dependencies import get_current_user
from app.auth.models import User

router = APIRouter()

@router.post("/submit_form")
async def submit_form(
    payload: FormData,
    db: Session = Depends(get_db_custom),
    user: Optional[User] = Depends(ApiLimiter),  # 自动限流和日志记录
):
    """
    用于 /api/submit_form 的用戶自定表單提交，寫入數據庫supplements.db。
    :param payload: locations-寫入的地點
    - region-寫入的音典分區（輸入完整的音典分區，例如嶺南-珠江-莞寶）
    - coordinates-寫入的經緯度坐標
    - feature-寫入的特徵（例如流攝等）
    - value-寫入的值（例如iu等）
    - description-寫入的具體說明
    - created_at：創建時間，後端自動生成，不填
    :param db: 存儲用戶寫入的orm
    :param user: 後端校驗得到的用戶身份
    :return: - 無返回值
    """
    # 限流和日志记录已由中间件和依赖注入自动处理

    try:
        result = handle_form_submission(payload.dict(), user, db)
        if not result.get("success"):
            raise HTTPException(status_code=422, detail=result.get("message"))
        return result
    except HTTPException:
        raise  # [OK] 让 HTTPException 保持原样传递
    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail="伺服器錯誤")
    finally:
        print("submit_form")

@router.delete("/delete_form")
async def delete_form(
    payload: FormData,
    db: Session = Depends(get_db_custom),
    user: Optional[User] = Depends(ApiLimiter),  # 自动限流和日志记录
):
    """
    用于 /api/delete_form 的用戶自定表單刪除。
    :param payload: locations-寫入的地點，要填
    - region-不填
    - coordinates-不填
    - feature-要填
    - value-要填
    - description-不用填
    - created_at：創建時間，後端根據時間+用戶名去刪。必填
    :param db: 存儲用戶寫入的orm
    :param user: 後端校驗得到的用戶身份
    :return: - 無返回值
    """
    # 限流和日志记录已由中间件和依赖注入自动处理

    try:
        result = handle_form_deletion(payload.dict(), user, db)
        if not result.get("success"):
            raise HTTPException(status_code=422, detail=result.get("message"))
        return result
    except HTTPException:
        raise  # [OK] 让 HTTPException 保持原样传递
    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail="伺服器錯誤")
    finally:
        print("delete_form")