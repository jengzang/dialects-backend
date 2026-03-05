
from fastapi import FastAPI, Depends
from .sql_routes import router as sql_router
from .sql_tree_routes import router as sql_tree_router
from app.logging.dependencies.limiter import ApiLimiter

def setup_sql_routes(app: FastAPI):
    app.include_router(sql_router, prefix="/sql", tags=["sql"], dependencies=[Depends(ApiLimiter)])
    app.include_router(sql_tree_router, prefix="/sql", tags=["sql"], dependencies=[Depends(ApiLimiter)])