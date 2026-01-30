# app/routes/get_regions.py

from fastapi import APIRouter, Request, Query, Depends
from typing import List, Union, Optional

from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.custom.database import get_db
from app.service.locs_regions import fetch_dialect_region
from app.logs.api_logger import log_all_fields

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
    # update_count(request.url.path)
    log_all_fields(request.url.path, {"input_data": input_data})
    # start = time.time()
    try:
        return fetch_dialect_region(input_data, db=db, user=user)
    finally:
        print("get_regions")
        # duration = time.time() - start
        # log_detailed_api(
        #     request.url.path,
        #     duration,
        #     200,
        #     request.client.host,
        #     request.headers.get("user-agent", ""),
        #     request.headers.get("referer", "")
        # )
