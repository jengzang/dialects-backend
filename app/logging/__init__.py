"""
日誌系統模塊

提供日誌記錄、統計、查詢等功能
"""
from fastapi import FastAPI, Depends


def setup_logs_routes(app: FastAPI):
    """註冊日誌統計路由"""
    # Import here to avoid circular dependency
    from app.routes.logging.stats import router as stats_router
    from app.routes.logging.hourly_daily import router as hourly_daily_router
    from app.logging.dependencies import ApiLimiter

    app.include_router(
        stats_router,
        prefix="/api/logs",
        tags=["日誌統計"],
        dependencies=[Depends(ApiLimiter)]
    )
    app.include_router(
        hourly_daily_router,
        prefix="/api/logs",
        tags=["日誌統計"],
        dependencies=[Depends(ApiLimiter)]
    )

