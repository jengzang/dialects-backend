import asyncio

import pytest
from fastapi import FastAPI


def test_startup_waits_until_other_worker_finishes_warmup(monkeypatch):
    from app.service.vocabulary import cache_warmup
    calls = 0
    monkeypatch.setattr(cache_warmup, 'get_vocabulary_cache', lambda path: object())
    async def warm(*args):
        nonlocal calls
        calls += 1
        return calls > 31
    async def sleep(seconds):
        return
    monkeypatch.setattr(cache_warmup, 'warm_once', warm)
    monkeypatch.setattr(cache_warmup.asyncio, 'sleep', sleep)
    async def scenario():
        handle = await cache_warmup.start_vocabulary_warmup()
        assert calls == 32
        await cache_warmup.stop_vocabulary_warmup(handle)
    asyncio.run(scenario())


@pytest.mark.parametrize("worker", [True, False])
def test_main_lifespan_starts_and_drains_warmup_in_every_web_worker(monkeypatch, worker):
    from app import main
    from app.service.vocabulary import cache_warmup
    calls = []
    monkeypatch.setattr(main, "_RUN_TYPE", "MINE")
    monkeypatch.setattr(main, "is_gunicorn_worker_process", lambda: worker)
    monkeypatch.setattr(main, "start_background_services", lambda: None)
    monkeypatch.setattr(main, "stop_background_services", lambda: None)
    async def start():
        calls.append("start")
        return "owned-handle"
    async def stop(handle):
        assert handle == "owned-handle"
        calls.append("stop")
    async def shutdown():
        calls.append("shutdown")
    monkeypatch.setattr(cache_warmup, "start_vocabulary_warmup", start)
    monkeypatch.setattr(cache_warmup, "stop_vocabulary_warmup", stop)
    monkeypatch.setattr(main, "shutdown_process_resources", shutdown)
    async def run():
        lifespan = main._build_lifespan(lambda: None, enable_background_services=True)
        async with lifespan(FastAPI()):
            assert calls == ["start"]
    asyncio.run(run())
    assert calls == ["start", "stop", "shutdown"]


def test_gis_lifespan_does_not_start_vocabulary_warmup(monkeypatch):
    from app import main
    from app.service.vocabulary import cache_warmup
    async def unexpected():
        pytest.fail("Separate app must not start vocabulary warmup")
    async def shutdown():
        pass
    monkeypatch.setattr(cache_warmup, "start_vocabulary_warmup", unexpected)
    monkeypatch.setattr(main, "shutdown_process_resources", shutdown)
    async def run():
        async with main._build_lifespan(lambda: None, enable_background_services=False)(FastAPI()):
            pass
    asyncio.run(run())
