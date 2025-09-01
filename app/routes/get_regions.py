# app/routes/get_regions.py

from fastapi import APIRouter, Request, Query, Depends
from typing import List, Union, Optional

from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.custom.database import get_db
from app.service.locs_regions import fetch_dialect_region
from app.service.api_logger import update_count
import time

router = APIRouter()

@router.get("/get_regions")
async def get_regions(
    request: Request,
    input_data: Union[str, List[str]] = Query(..., alias="input_data"),
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_user)
):
    """
    - :param request:地點簡稱
    - :return: 對應的音典分區
    """
    update_count(request.url.path)
    start = time.time()
    try:
        return fetch_dialect_region(input_data, db=db, user=user)
    finally:
        duration = time.time() - start

