from fastapi import APIRouter, Depends
from .custom import router as custom_router
from app.logging.dependencies.limiter import ApiLimiter

router = APIRouter()

router.include_router(custom_router, prefix="/custom", dependencies=[Depends(ApiLimiter)])
