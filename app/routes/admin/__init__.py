from fastapi import APIRouter, Depends

# 导入每个模块
from .users import router as users_router
from .user_stats import router as stats_router
from .api_usage import router as api_usage_router
from .login_logs import router as login_logs_router
from .custom import router as custom_router
from .custom_edit import router as custom_edit_router
from .sessions import router as sessions_router
from .cache_manager import router as cache_manager_router
from ...auth.dependencies import get_current_admin_user
from ..admin.get_ip import router as get_ip

# 创建一个总的 admin 路由集合
router = APIRouter()

router.include_router(users_router, prefix="/users", tags=["admin users"],
                      dependencies=[Depends(get_current_admin_user)])
router.include_router(stats_router, prefix="/stats", tags=["admin stats"],
                      dependencies=[Depends(get_current_admin_user)])
router.include_router(api_usage_router, prefix="/api-usage", tags=["admin api usage"],
                      dependencies=[Depends(get_current_admin_user)])
router.include_router(login_logs_router, prefix="/login-logs", tags=["admin stats"],
                      dependencies=[Depends(get_current_admin_user)])
router.include_router(custom_router, prefix="/custom", tags=["admin custom"],
                      dependencies=[Depends(get_current_admin_user)])
router.include_router(custom_edit_router, prefix="/custom", tags=["admin custom"],
                      dependencies=[Depends(get_current_admin_user)])
router.include_router(sessions_router, prefix="/sessions", tags=["admin sessions"],
                      dependencies=[Depends(get_current_admin_user)])
router.include_router(get_ip, prefix="/ip", tags=["admin api usage"],
                      dependencies=[Depends(get_current_admin_user)])
router.include_router(cache_manager_router, prefix="/cache", tags=["admin cache"],
                      dependencies=[Depends(get_current_admin_user)])
