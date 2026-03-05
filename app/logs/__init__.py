# logs package
from fastapi import FastAPI, Depends


def setup_logs_routes(app: FastAPI):
    """注册日志统计路由"""
    # Import here to avoid circular dependency
    from app.routes.logs.stats import router as logs_stats_router
    from app.routes.logs.hourly_daily import router as hourly_daily_router
    from app.logs.service.api_limiter import ApiLimiter

    app.include_router(logs_stats_router, dependencies=[Depends(ApiLimiter)])
    app.include_router(hourly_daily_router, dependencies=[Depends(ApiLimiter)])
