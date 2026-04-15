# app/main.py
import asyncio
import os
import threading
import time
from contextlib import asynccontextmanager

from app.common.numba_bootstrap import bootstrap_numba_threading_environment
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.staticfiles import StaticFiles

bootstrap_numba_threading_environment()

from app.common.config import _RUN_TYPE
from app.lifecycle import (
    is_gunicorn_worker_process,
    run_process_startup,
    shutdown_process_resources,
    start_background_services,
    stop_background_services,
)
from app.routes import setup_routes
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    if _RUN_TYPE == "EXE":
        global _printer_started
        if not _printer_started:
            _printer_started = True
            threading.Thread(target=_periodic_printer, daemon=True).start()

    run_process_startup()

    is_gunicorn_worker = is_gunicorn_worker_process()
    if not is_gunicorn_worker:
        print("[MODE] Starting single-process background services...")
        start_background_services()
    else:
        print("[SKIP] Worker process skips background service startup")

    try:
        yield
    finally:
        if not is_gunicorn_worker:
            stop_background_services()
            print("[STOP] Single-process background services stopped")
        else:
            print("[SKIP] Worker process skips background service shutdown")

        print("[STOP] App shutting down...")
        try:
            await shutdown_process_resources()
        except asyncio.CancelledError:
            print("[WARN] Shutdown cancelled while releasing process resources")
        except KeyboardInterrupt:
            print("[WARN] Shutdown interrupted while releasing process resources")


def create_app() -> FastAPI:
    if _RUN_TYPE in ["EXE", "MINE"]:
        app = FastAPI(lifespan=lifespan)
    else:
        app = FastAPI(docs_url=None, redoc_url=None, lifespan=lifespan)

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

    setup_routes(app)
    app.mount("", StaticFiles(directory=os.path.abspath("app/statics"), html=True), name="static")

    if _RUN_TYPE == "EXE":
        app.mount("/data", StaticFiles(directory=ensure_user_data()), name="data")

    return app


app = create_app()
