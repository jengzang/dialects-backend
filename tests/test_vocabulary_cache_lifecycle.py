import asyncio

import pytest
from fastapi import FastAPI


def test_startup_returns_while_background_warmup_is_still_running(monkeypatch):
    from app.service.vocabulary import cache_warmup
    monkeypatch.setattr(cache_warmup, 'get_vocabulary_cache', lambda path: object())
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        async def warm(*args, **kwargs):
            entered.set()
            await release.wait()
            return True
        monkeypatch.setattr(cache_warmup, 'warm_once', warm)
        handle = None
        try:
            handle = await asyncio.wait_for(cache_warmup.start_vocabulary_warmup(), .5)
            await asyncio.wait_for(entered.wait(), .5)
            assert not handle[0].done()
        finally:
            release.set()
            if handle is not None:
                await cache_warmup.stop_vocabulary_warmup(handle)
                assert handle[1] not in cache_warmup._wakeups
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
