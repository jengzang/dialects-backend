from fastapi import APIRouter
from .custom import router as custom_router

router = APIRouter()

router.include_router(custom_router, prefix="/custom", tags=["User Custom"])
