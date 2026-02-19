# app/routes/get_regions.py

from fastapi import APIRouter, Query, Depends
from typing import List, Union, Optional

from sqlalchemy.orm import Session

from app.auth.models import User
from app.custom.database import get_db
from app.service.locs_regions import fetch_dialect_region
from app.logs.service.api_limiter import ApiLimiter

router = APIRouter()

@router.get("/get_regions")
async def get_regions(
    input_data: Union[str, List[str]] = Query(..., alias="input_data"),
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(ApiLimiter)  # 自动限流和日志记录
):
    """
    - :param input_data:地點簡稱
    - :return: 對應的音典分區
    """
    # 限流和日志记录已由中间件和依赖注入自动处理
    try:
        return fetch_dialect_region(input_data, db=db, user=user)
    finally:
        print("get_regions")
