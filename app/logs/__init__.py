# logs package
from fastapi import FastAPI

from.logs_stats import router as logs_stats_router  # [OK] 新增日志统计路由

def setup_logs_routes(app: FastAPI):
    app.include_router(logs_stats_router, prefix="/logs", tags=["日志统计"])  # [OK] 注册日志统计路由