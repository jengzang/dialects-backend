"""Single-host admission before thread dispatch; complete accepted work on cancellation.

Shares the two toponyms heavy slots. Vocabulary adds one expensive-work slot,
one writer per database, and eight waiting requests across workers. Only admission
has a 30s timeout; accepted full-result work has no execution deadline or retry.
"""
import asyncio
from contextlib import ExitStack
from functools import wraps
from inspect import signature
import time

import anyio
from fastapi import HTTPException

from app.common.path import TOPONYMS_DB_PATH
from app.service.toponyms.resources import _slot, QueryBusy


class BackgroundBusy(Exception):
    """Background work yields to occupied slots instead of joining request waiters."""


async def run_bounded(db_path, operation, *args, write=False, expensive=False, background=False, **kwargs):
    slots = ExitStack()
    try:
        def acquire():
            if expensive:
                slots.enter_context(_slot(TOPONYMS_DB_PATH, 'vocabulary-expensive', 1))
            if write:
                slots.enter_context(_slot(db_path, 'vocabulary-writer', 1))
            slots.enter_context(_slot(TOPONYMS_DB_PATH, 'heavy', 2))

        if background:
            # One attempt; never occupy an online waiter or a polling thread.
            acquire()
        else:
            with _slot(TOPONYMS_DB_PATH, 'vocabulary-waiters', 8):
                deadline = time.monotonic() + 30
                while True:
                    try:
                        acquire()
                        break
                    except QueryBusy:
                        slots.close()
                        if time.monotonic() >= deadline:
                            raise
                        await asyncio.sleep(.05)
        task = asyncio.create_task(asyncio.to_thread(operation, *args, **kwargs))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            # Never close a Session/release a lease while its thread is committing.
            with anyio.CancelScope(shield=True):
                while not task.done():
                    try:
                        await asyncio.shield(task)
                    except asyncio.CancelledError:
                        continue
                    except Exception:
                        break
                if not task.cancelled() and task.exception() is None:
                    result = task.result()
                    cleanup = getattr(result, 'cleanup', None)
                    if cleanup is not None:
                        cleanup()
            raise
    except QueryBusy as exc:
        if background:
            raise BackgroundBusy() from exc
        raise HTTPException(status_code=503, detail='词表任务繁忙，请稍后重试',
                            headers={'Retry-After': '1'}) from exc
    finally:
        slots.close()


def bounded_operation(*, write=False, expensive=False):
    """Keep FastAPI's parameter/dependency signature while offloading a sync unit."""
    def decorate(operation):
        params = signature(operation)
        @wraps(operation)
        async def wrapped(*args, **kwargs):
            bound = params.bind(*args, **kwargs)
            db = bound.arguments['db']
            path = db.get_bind().url.database
            def execute():
                try:
                    return operation(*args, **kwargs)
                except BaseException:
                    db.rollback()
                    raise
            return await run_bounded(path, execute, write=write, expensive=expensive)
        return wrapped
    return decorate
