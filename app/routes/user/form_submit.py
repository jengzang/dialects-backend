# routes/form_submit.py
"""
[PKG] 璺敱妯″锛氳檿鐞?/api/submit_form 鎻愪氦鐢ㄦ埗濉鐨勮獮闊宠硣鏂欍€?"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.service.user.core.database import get_db as get_db_custom
from app.service.user.submission.delete import handle_form_deletion
from app.schemas import FormData
from app.service.user.submission.submit import handle_form_submission
from app.service.auth.core.dependencies import get_current_user
# from app.logging.dependencies.limiter import ApiLimiter
from app.service.auth.database.models import User

router = APIRouter()

@router.post("/submit_form")
async def submit_form(
    payload: FormData,
    db: Session = Depends(get_db_custom),
    user: Optional[User] = Depends(get_current_user)
):
    """Handle user custom form submission."""
    try:
        result = handle_form_submission(payload.dict(), user, db)
        if not result.get("success"):
            raise HTTPException(status_code=422, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail="服务器错误")
    finally:
        print("submit_form")
@router.delete("/delete_form")
async def delete_form(
    payload: FormData,
    db: Session = Depends(get_db_custom),
    user: Optional[User] = Depends(get_current_user)
):
    """
    用于 /api/delete_form 的用户自定义表单删除。
    """
    try:
        if user is None:
            raise HTTPException(status_code=401, detail="未登录用户没有权限执行删除操作")

        result = handle_form_deletion(payload.dict(), user, db)
        if not result.get("success"):
            raise HTTPException(status_code=422, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail="服务器错误")
    finally:
        print("delete_form")

