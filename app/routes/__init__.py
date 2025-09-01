# routes/__init__.py
"""
📦 路由註冊模塊：將所有子路由模組掛載到 FastAPI app。
"""

from fastapi import FastAPI
from .phonology import router as phonology_router
from .get_regions import router as region_router
from .get_partitions import router as partitions_router
from .batch_match import router as batch_match_router
from .get_coordinates import router as coordinates_router
from .form_submit import router as form_router
from .custom_query import router as custom_query_router
from .search import router as search_router
from .index import router as index_router
from .auth import router as auth_router
from .get_locs import router as locs_router



def setup_routes(app: FastAPI):
    app.include_router(phonology_router, prefix="/api", tags=["query"])
    app.include_router(partitions_router, prefix="/api")
    app.include_router(region_router, prefix="/api")
    app.include_router(batch_match_router, prefix="/api")
    app.include_router(coordinates_router, prefix="/api")
    app.include_router(form_router, prefix="/api", tags=["custom"])
    app.include_router(custom_query_router, prefix="/api", tags=["custom"])
    app.include_router(search_router, prefix="/api", tags=["query"])
    app.include_router(index_router)
    app.include_router(locs_router, prefix="/api")
    app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
