from fastapi import APIRouter, Depends

# 导入每个模块（按新的目录结构）
# Users
from .users.crud import router as users_router
from .users.stats import router as stats_router
from .users.permissions import router as permissions_router

# Sessions
from .sessions.management import router as user_sessions_router
from .sessions.legacy import router as sessions_legacy_router

# Submissions (原 custom)
from .submissions.data import router as submissions_data_router
from .submissions.regions import router as submissions_regions_router

# Analytics
from .analytics.overview import router as analytics_router
from .analytics.api_usage import router as api_usage_router
from .analytics.leaderboard import router as leaderboard_router
from .analytics.login_logs import router as login_logs_router

# System
from .system.cache import router as cache_router
from .system.ip_lookup import router as ip_lookup_router

from app.service.auth.core.dependencies import get_current_admin_user

# 创建一个总的 admin 路由集合
router = APIRouter()

# ========== Users ==========
router.include_router(users_router, prefix="/users", tags=["admin users"],
                      dependencies=[Depends(get_current_admin_user)])
router.include_router(stats_router, prefix="/stats", tags=["admin stats"],
                      dependencies=[Depends(get_current_admin_user)])
router.include_router(permissions_router, prefix="/permissions", tags=["admin users"],
                      dependencies=[Depends(get_current_admin_user)])

# ========== Sessions ==========
# ✅ 推荐：基于 Session 模型的会话管理 API
router.include_router(user_sessions_router, prefix="/user-sessions", tags=["admin user-sessions"],
                      dependencies=[Depends(get_current_admin_user)])
# ⚠️ Legacy：基于 RefreshToken 的会话管理（保持向后兼容）
router.include_router(sessions_legacy_router, prefix="/sessions", tags=["admin sessions (legacy)"],
                      dependencies=[Depends(get_current_admin_user)])

# ========== Submissions (原 custom) ==========
router.include_router(submissions_data_router, prefix="/custom", tags=["admin submissions"],
                      dependencies=[Depends(get_current_admin_user)])
router.include_router(submissions_regions_router, prefix="/custom-regions", tags=["admin submissions"],
                      dependencies=[Depends(get_current_admin_user)])

# ========== Analytics ==========
router.include_router(analytics_router, prefix="/analytics", tags=["admin analytics"],
                      dependencies=[Depends(get_current_admin_user)])
router.include_router(api_usage_router, prefix="/api-usage", tags=["admin analytics"],
                      dependencies=[Depends(get_current_admin_user)])
router.include_router(leaderboard_router, prefix="/leaderboard", tags=["admin analytics"],
                      dependencies=[Depends(get_current_admin_user)])
router.include_router(login_logs_router, prefix="/login-logs", tags=["admin analytics"],
                      dependencies=[Depends(get_current_admin_user)])

# ========== System ==========
router.include_router(cache_router, prefix="/cache", tags=["admin system"],
                      dependencies=[Depends(get_current_admin_user)])
router.include_router(ip_lookup_router, prefix="/ip", tags=["admin system"],
                      dependencies=[Depends(get_current_admin_user)])
