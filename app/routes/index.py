# routes/index.py
"""
[PKG] Route module for serving static SPA entry pages.
"""

from fastapi import APIRouter, Request
from starlette.responses import HTMLResponse

from app.service.logging.stats.html_visit_pipeline import update_html_visit
from app.static_utils import get_resource_path

router = APIRouter()


def _serve_html(request: Request, resource_path: str) -> HTMLResponse:
    update_html_visit(request.url.path)
    index_path = get_resource_path(resource_path)
    with open(index_path, encoding="utf-8") as f:
        content = f.read()
    headers = {"Cache-Control": "no-cache, must-revalidate"}
    return HTMLResponse(content=content, headers=headers)


def _register_spa_route(base_path: str, resource_path: str) -> None:
    async def serve_base(request: Request) -> HTMLResponse:
        return _serve_html(request, resource_path)

    async def serve_nested(request: Request, _: str) -> HTMLResponse:
        return _serve_html(request, resource_path)

    router.add_api_route(base_path, serve_base, methods=["GET"], response_class=HTMLResponse, tags=["html"])
    router.add_api_route(
        f"{base_path}/{{_:path}}",
        serve_nested,
        methods=["GET"],
        response_class=HTMLResponse,
        tags=["html"],
    )


@router.get("/", response_class=HTMLResponse, tags=["html"])
async def root_index(request: Request) -> HTMLResponse:
    return _serve_html(request, "app/statics/index.html")


_register_spa_route("/intro", "app/statics/intro/index.html")
_register_spa_route("/menu", "app/statics/menu/index.html")
_register_spa_route("/explore", "app/statics/explore/index.html")
_register_spa_route("/villagesML", "app/statics/villagesML/index.html")
_register_spa_route("/auth", "app/statics/auth/index.html")


@router.get("/detail", response_class=HTMLResponse, tags=["html"])
async def detail_index(request: Request) -> HTMLResponse:
    return _serve_html(request, "app/statics/detail/index.html")


@router.get("/admin", response_class=HTMLResponse, tags=["html"])
async def admin_index(request: Request) -> HTMLResponse:
    return _serve_html(request, "app/statics/admin/index.html")


@router.get("/__ping")
def ping():
    return "ok"
