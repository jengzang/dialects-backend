# app/main.py
import asyncio
import os
import threading
import time
from contextlib import asynccontextmanager
from typing import Callable

from app.common.numba_bootstrap import bootstrap_numba_threading_environment
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.responses import FileResponse
from starlette.staticfiles import StaticFiles

bootstrap_numba_threading_environment()

from app.common.config import _RUN_TYPE
from app.lifecycle import (
    is_gunicorn_worker_process,
    run_cluster_startup,
    run_gis_startup,
    run_main_startup,
    shutdown_process_resources,
    start_background_services,
    stop_background_services,
)
from app.routes import setup_cluster_routes, setup_gis_routes, setup_routes
from app.service.logging.middleware.traffic_logging import RequestLogMiddleware
from app.static_utils import ensure_user_data

if _RUN_TYPE == "EXE":
    print_lock = threading.Lock()
    active_requests = 0
    _printer_started = False

    def _periodic_printer():
        msg = (
            "\n\n##################################\n"
            "Backend process is alive.\n"
            "This window must stay open in EXE mode.\n"
            "###################################"
        )
        while True:
            time.sleep(200)
            with print_lock:
                if active_requests == 0:
                    print(msg)
                    now = time.strftime("%Y-%m-%d %H:%M:%S")
                    print(f"[{now}] Backend alive [OK]")


def _build_lifespan(
    startup_fn: Callable[[], None],
    *,
    enable_background_services: bool,
):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if _RUN_TYPE == "EXE":
            global _printer_started
            if not _printer_started:
                _printer_started = True
                threading.Thread(target=_periodic_printer, daemon=True).start()

        startup_fn()

        is_gunicorn_worker = is_gunicorn_worker_process()
        should_manage_background = enable_background_services and not is_gunicorn_worker
        if should_manage_background:
            print("[MODE] Starting single-process background services...")
            start_background_services()
        elif enable_background_services:
            print("[SKIP] Worker process skips background service startup")
        else:
            print("[SKIP] App profile disables background service startup")

        try:
            yield
        finally:
            if should_manage_background:
                stop_background_services()
                print("[STOP] Single-process background services stopped")
            elif enable_background_services:
                print("[SKIP] Worker process skips background service shutdown")
            else:
                print("[SKIP] App profile disables background service shutdown")

            print("[STOP] App shutting down...")
            try:
                await shutdown_process_resources()
            except asyncio.CancelledError:
                print("[WARN] Shutdown cancelled while releasing process resources")
            except KeyboardInterrupt:
                print("[WARN] Shutdown interrupted while releasing process resources")

    return lifespan


_LOCALE_PREFIXES = ("en", "zh-Hant", "zh-CN")

# 所有後端路由前綴，SPA 兜底時不能攔截這些路徑（即使 404 也該正常返回）
_BACKEND_PREFIXES = (
    "/api",
    "/admin",
    "/user",
    "/sql",
    "/logs",
    "/__ping",
)


def _is_backend_path(path: str) -> bool:
    for p in _BACKEND_PREFIXES:
        if path == p or path.startswith(f"{p}/") or path.startswith(f"{p}?"):
            return True
    return False


def _apply_common_middlewares(app: FastAPI) -> None:
    if _RUN_TYPE == "WEB":
        cors_origins = ["https://dialects.yzup.top", "https://yzup.top"]
    else:
        cors_origins = ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(RequestLogMiddleware)

    @app.middleware("http")
    async def strip_locale_prefix(request: Request, call_next):
        path = request.url.path
        for loc in _LOCALE_PREFIXES:
            # /zh-CN/xxx → /xxx,  /zh-CN → /,  /zh-CN/ → /
            prefix = f"/{loc}"
            if path == prefix or path.startswith(f"{prefix}/"):
                path = path[len(prefix):] or "/"
                request.scope["path"] = path
                request.scope["raw_path"] = path.encode()
                break

        response = await call_next(request)

        if response.status_code == 404 and request.method == "GET" and not _is_backend_path(path):
            return FileResponse(os.path.abspath("app/statics/index.html"))

        return response

    if _RUN_TYPE == "EXE":

        @app.middleware("http")
        async def pause_print_while_request(request: Request, call_next):
            global active_requests
            with print_lock:
                active_requests += 1
            try:
                response = await call_next(request)
                return response
            finally:
                with print_lock:
                    active_requests -= 1


def _mount_static(app: FastAPI, *, enable_static_mounts: bool) -> None:
    if not enable_static_mounts:
        return

    app.mount("", StaticFiles(directory=os.path.abspath("app/statics"), html=True), name="static")

    if _RUN_TYPE == "EXE":
        app.mount("/data", StaticFiles(directory=ensure_user_data()), name="data")


def _create_app(*, startup_fn: Callable[[], None], route_setup_fn: Callable[[FastAPI], None], enable_background_services: bool, enable_static_mounts: bool) -> FastAPI:
    lifespan = _build_lifespan(startup_fn, enable_background_services=enable_background_services)
    if _RUN_TYPE in ["EXE", "MINE"]:
        app = FastAPI(lifespan=lifespan)
    else:
        app = FastAPI(docs_url=None, redoc_url=None, lifespan=lifespan)

    _apply_common_middlewares(app)
    route_setup_fn(app)
    _mount_static(app, enable_static_mounts=enable_static_mounts)
    return app


def create_main_app() -> FastAPI:
    return _create_app(
        startup_fn=run_main_startup,
        route_setup_fn=setup_routes,
        enable_background_services=True,
        enable_static_mounts=True,
    )


def create_gis_app() -> FastAPI:
    # 暂时关闭 GIS 独立应用入口，避免任何部署/容器路径误启用重内存 GIS 引擎。
    # 如需恢复，请重新启用 app.routes.setup_gis_routes 与 run_gis_startup。
    return _create_app(
        startup_fn=run_main_startup,
        route_setup_fn=lambda app: None,
        enable_background_services=False,
        enable_static_mounts=False,
    )


def create_cluster_app() -> FastAPI:
    return _create_app(
        startup_fn=run_cluster_startup,
        route_setup_fn=setup_cluster_routes,
        enable_background_services=False,
        enable_static_mounts=False,
    )


def create_app() -> FastAPI:
    return create_main_app()


app = create_app()
