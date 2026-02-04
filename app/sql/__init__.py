
from fastapi import FastAPI
from .sql_routes import router as sql_router
from .sql_tree_routes import router as sql_tree_router

def setup_sql_routes(app: FastAPI):
    app.include_router(sql_router, prefix="/sql",tags=["sql"])
    app.include_router(sql_tree_router, prefix="/sql", tags=["sql"])