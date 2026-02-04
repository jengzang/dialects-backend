# routes/index.py
"""
[PKG] 路由模塊：處理根路由 / 返回 index.html 靜態頁面。
"""

from fastapi import APIRouter, Request
from starlette.responses import HTMLResponse
from app.statics.static_utils import get_resource_path
from app.logs.api_logger import update_html_visit
# from common.config import HTML_PATH

router = APIRouter()

@router.get("/", response_class=HTMLResponse, tags=["html"])
async def index(request: Request):
    update_html_visit(request.url.path)
    # print(request.url.path)
    index_path = get_resource_path("app/statics/index.html")
    with open(index_path, encoding="utf-8") as f:
        content = f.read()
    headers = {"Cache-Control": "no-cache, must-revalidate"}
    return HTMLResponse(content=content, headers=headers)

@router.get("/detail", response_class=HTMLResponse, tags=["html"])
async def index(request: Request):
    update_html_visit(request.url.path)
    index_path = get_resource_path("app/statics/detail/index.html")
    with open(index_path, encoding="utf-8") as f:
        content = f.read()
    headers = {"Cache-Control": "no-cache, must-revalidate"}
    return HTMLResponse(content=content, headers=headers)

@router.get("/admin", response_class=HTMLResponse, tags=["html"])
async def index(request: Request):
    update_html_visit(request.url.path)
    index_path = get_resource_path("app/statics/admin/index.html")
    with open(index_path, encoding="utf-8") as f:
        content = f.read()
    headers = {"Cache-Control": "no-cache, must-revalidate"}
    return HTMLResponse(content=content, headers=headers)

@router.get("/intro", response_class=HTMLResponse, tags=["html"])
async def index(request: Request):
    update_html_visit(request.url.path)
    index_path = get_resource_path("app/statics/intro/index.html")
    with open(index_path, encoding="utf-8") as f:
        content = f.read()
    headers = {"Cache-Control": "no-cache, must-revalidate"}
    return HTMLResponse(content=content, headers=headers)

@router.get("/menu", response_class=HTMLResponse, tags=["html"])
async def index(request: Request):
    update_html_visit(request.url.path)
    index_path = get_resource_path("app/statics/menu/index.html")
    with open(index_path, encoding="utf-8") as f:
        content = f.read()
    headers = {"Cache-Control": "no-cache, must-revalidate"}
    return HTMLResponse(content=content, headers=headers)

@router.get("/explore", response_class=HTMLResponse, tags=["html"])
async def index(request: Request):
    update_html_visit(request.url.path)
    index_path = get_resource_path("app/statics/explore/index.html")
    with open(index_path, encoding="utf-8") as f:
        content = f.read()
    headers = {"Cache-Control": "no-cache, must-revalidate"}
    return HTMLResponse(content=content, headers=headers)

@router.get("/auth", response_class=HTMLResponse, tags=["html"])
async def index(request: Request):
    update_html_visit(request.url.path)
    index_path = get_resource_path("app/statics/auth/index.html")
    with open(index_path, encoding="utf-8") as f:
        content = f.read()
    headers = {"Cache-Control": "no-cache, must-revalidate"}
    return HTMLResponse(content=content, headers=headers)

@router.get("/__ping")
def ping():
    return "ok"

