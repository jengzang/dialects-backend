from __future__ import annotations

from threading import Lock

from app.geo_query.engine import ENGINE

_INIT_LOCK = Lock()


def load_geo_query_engine() -> None:
    if ENGINE.loaded:
        return
    with _INIT_LOCK:
        if not ENGINE.loaded:
            ENGINE.init_store_in_wkb_file()


def get_geo_engine():
    load_geo_query_engine()
    return ENGINE
