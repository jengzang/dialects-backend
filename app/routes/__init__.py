# routes/__init__.py
"""
[PKG] 路由註冊模塊：將所有子路由模組掛載到 FastAPI app。
"""

from fastapi import FastAPI, Depends
from app.routes.core.phonology import router as phonology_router
from app.routes.core.new_pho import router as new_pho_router
from app.routes.geo.get_regions import router as region_router
from app.routes.geo.get_partitions import router as partitions_router
from app.routes.geo.batch_match import router as batch_match_router
from app.routes.geo.get_coordinates import router as coordinates_router
from app.routes.user.form_submit import router as form_router
from app.routes.user.custom_query import router as custom_query_router
from app.routes.user.custom_regions import router as custom_regions_router
from app.routes.core.search import router as search_router
from app.routes.core.compare import router as compare_router
from .index import router as index_router
from .auth import router as auth_router
from app.routes.geo.get_locs import router as locs_router
from .admin import router as admin_router
from .user import router as user_router
from app.service.logging import setup_logs_routes
from ..sql import setup_sql_routes
from app.tools import setup_tools_routes
from app.tools.praat.routes import router as praat_router
from app.service.logging.dependencies import ApiLimiter
from app.villagesML import setup_villages_routes


def setup_routes(app: FastAPI):
    app.include_router(phonology_router, prefix="/api", tags=["query"], dependencies=[Depends(ApiLimiter)])
    app.include_router(new_pho_router, prefix="/api", tags=["query"], dependencies=[Depends(ApiLimiter)])
    app.include_router(partitions_router, prefix="/api", tags=["geo"], dependencies=[Depends(ApiLimiter)])
    app.include_router(region_router, prefix="/api", tags=["geo"], dependencies=[Depends(ApiLimiter)])
    app.include_router(batch_match_router, prefix="/api", tags=["geo"], dependencies=[Depends(ApiLimiter)])
    app.include_router(coordinates_router, prefix="/api", tags=["geo"], dependencies=[Depends(ApiLimiter)])
    app.include_router(form_router, prefix="/api", tags=["custom"], dependencies=[Depends(ApiLimiter)])
    app.include_router(custom_query_router, prefix="/api", tags=["custom"], dependencies=[Depends(ApiLimiter)])
    app.include_router(custom_regions_router, tags=["custom"], dependencies=[Depends(ApiLimiter)])
    app.include_router(search_router, prefix="/api", tags=["query"], dependencies=[Depends(ApiLimiter)])
    app.include_router(compare_router, prefix="/api", tags=["query"], dependencies=[Depends(ApiLimiter)])
    app.include_router(index_router, dependencies=[Depends(ApiLimiter)])
    app.include_router(locs_router, prefix="/api", tags=["geo"], dependencies=[Depends(ApiLimiter)])
    app.include_router(auth_router, prefix="/auth", tags=["Authentication"], dependencies=[Depends(ApiLimiter)])
    app.include_router(admin_router, prefix="/admin")
    app.include_router(user_router, prefix="/user", tags=["User"], dependencies=[Depends(ApiLimiter)])

    # Praat acoustic analysis
    app.include_router(praat_router, dependencies=[Depends(ApiLimiter)])

    setup_tools_routes(app)
    setup_sql_routes(app)
    setup_logs_routes(app)
    setup_villages_routes(app)

