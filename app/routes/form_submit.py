# routes/form_submit.py
"""
📦 路由模塊：處理 /api/submit_form 提交用戶填寫的語音資料。
"""

from fastapi import APIRouter, Request, HTTPException, Depends


from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.custom.database import get_db as get_db_custom
from app.auth.database import get_db as get_db_user
from app.custom.delete import handle_form_deletion
from app.schemas import FormData
from app.custom.write_submit import handle_form_submission
import time
from app.service.api_logger import *
from common.config import CLEAR_WEEK

router = APIRouter()

@router.post("/submit_form")
async def submit_form(
    request: Request,
    payload: FormData,
    db: Session = Depends(get_db_custom),
    # db_user: Session = Depends(get_db_user),
    user: User = Depends(get_current_user)
):
    """
    用于 /api/submit_form 的用戶自定表單提交，寫入數據庫supplements.db。
    :param request: 傳token
    :param payload: locations-寫入的地點
    - region-寫入的音典分區（輸入完整的音典分區，例如嶺南-珠江-莞寶）
    - coordinates-寫入的經緯度坐標
    - feature-寫入的特徵（例如流攝等）
    - value-寫入的值（例如iu等）
    - description-寫入的具體說明
    - created_at：創建時間，後端自動生成，不填
    :param db: 存儲用戶寫入的orm
    :param db_user: 存儲用戶身份的orm
    :param user: 後端校驗得到的用戶身份
    :return: - 無返回值
    """
    update_count(request.url.path)
    log_all_fields(request.url.path, payload.dict())
    start = time.time()

    try:
        result = handle_form_submission(payload.dict(), user, db)
        if not result.get("success"):
            raise HTTPException(status_code=422, detail=result.get("message"))
        return result
    except HTTPException:
        raise  # ✅ 让 HTTPException 保持原样传递
    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail="伺服器錯誤")
    finally:
        duration = time.time() - start
        # path = request.url.path
        # ip = request.client.host
        # agent = request.headers.get("user-agent", "")
        # referer = request.headers.get("referer", "")
        # user_id = user.id if user else None
        log_detailed_api(
            request.url.path, duration, 200,
            request.client.host,
            request.headers.get("user-agent", ""),
            request.headers.get("referer", "")
        )
        # log_detailed_api_to_db(db_user, path,
        #                        duration, 200, ip,
        #                        agent, referer, user_id, CLEAR_2HOUR)

@router.delete("/delete_form")
async def delete_form(
    request: Request,
    payload: FormData,
    db: Session = Depends(get_db_custom),
    # db_user: Session = Depends(get_db_user),
    user: User = Depends(get_current_user)
):
    """
    用于 /api/submit_form 的用戶自定表單提交，寫入數據庫supplements.db。
    :param request: 傳token
    :param payload: locations-寫入的地點，要填
    - region-不填
    - coordinates-不填
    - feature-要填
    - value-要填
    - description-不用填
    - created_at：創建時間，後端根據時間+用戶名去刪。必填
    :param db: 存儲用戶寫入的orm
    :param db_user: 存儲用戶身份的orm
    :param user: 後端校驗得到的用戶身份
    :return: - 無返回值
    """
    update_count(request.url.path)
    log_all_fields(request.url.path, payload.dict())
    start = time.time()

    try:
        result = handle_form_deletion(payload.dict(), user, db)
        if not result.get("success"):
            raise HTTPException(status_code=422, detail=result.get("message"))
        return result
    except HTTPException:
        raise  # ✅ 让 HTTPException 保持原样传递
    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail="伺服器錯誤")
    finally:
        duration = time.time() - start
        # path = request.url.path
        # ip = request.client.host
        # agent = request.headers.get("user-agent", "")
        # referer = request.headers.get("referer", "")
        # user_id = user.id if user else None
        log_detailed_api(
            request.url.path, duration, 200,
            request.client.host,
            request.headers.get("user-agent", ""),
            request.headers.get("referer", "")
        )
        # log_detailed_api_to_db(db_user, path,
        #                        duration, 200, ip,
        #                        agent, referer, user_id, CLEAR_2HOUR)