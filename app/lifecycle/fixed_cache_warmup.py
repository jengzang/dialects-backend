"""One finite startup pass. Foreground cache misses never join this task."""
import asyncio
from dataclasses import dataclass
import logging
import threading
import time

from app.common import fixed_default_cache as cache
from app.service.fixed_defaults import load_on_connection, readonly as _readonly
from functools import partial

log = logging.getLogger(__name__)
ITEM_BUDGET_SECONDS = 30
ROUND_BUDGET_SECONDS = 120


@dataclass
class Warmup:
    task: asyncio.Task
    stop_event: threading.Event


def default_entries():
    from app.common.path import DB_MAPPING
    from app.villagesML.schema_config import DEFAULT_DATABASE_KEY
    from app.villagesML.schema_runtime import resolve_db_path
    paths = {
        "sql:query_stored_count": DB_MAPPING["query"],
        "sql:dialects_count": DB_MAPPING["dialects"],
        "yubao:vocabulary_all": DB_MAPPING["yubao"],
        "yubao:grammar_all": DB_MAPPING["yubao"],
        "villages:gd:ngrams": resolve_db_path(DEFAULT_DATABASE_KEY),
        "villages:gd:tables": resolve_db_path(DEFAULT_DATABASE_KEY),
    }
    return [(slot, path, partial(load_on_connection, slot, bounded_warmup=True))
            for slot, path in paths.items()]


def _run(entries, client, stopped):
    client = cache.client_or_default(client)
    round_deadline = time.monotonic() + ROUND_BUDGET_SECONDS
    with cache.publication_lock("warmup") as elected:
        if not elected:
            return
        # Wait only in the background, e.g. for an already running vocabulary warmer.
        while not stopped.is_set() and time.monotonic() < round_deadline:
            with cache.publication_lock() as acquired:
                if acquired:
                    return _warm_entries(entries, client, stopped, round_deadline)
            stopped.wait(0.05)


def _warm_entries(entries, client, stopped, round_deadline):
    entries = default_entries() if entries is None else entries
    for slot, path, loader in entries:
        if stopped.is_set() or time.monotonic() >= round_deadline:
            return
        try:
            if cache.lookup(slot, path, client) is not cache._MISSING:
                continue
        except Exception:
            log.warning("Fixed default warmup stopped: Redis unavailable")
            return
        stamp = cache.version(path, slot)
        if stamp is None:
            log.warning("Fixed default warmup missing database: %s", slot)
            continue
        deadline = min(round_deadline, time.monotonic() + ITEM_BUDGET_SECONDS)
        def expired():
            return stopped.is_set() or time.monotonic() >= deadline
        try:
            # mode=ro protects main database; TEMP schema views remain supported.
            with _readonly(path, expired) as db:
                result = loader(db)
                if expired():
                    raise TimeoutError("Fixed default warmup budget exceeded")
            if stopped.is_set():
                return
        except Exception:
            log.warning("Fixed default warmup skipped %s", slot, exc_info=True)
            continue
        try:
            cache.publish(slot, path, stamp, result, client)
        except Exception:
            log.warning("Fixed default warmup stopped: Redis publication failed")
            return


def start(*, entries=None, client=None):
    stopped = threading.Event()
    task = asyncio.create_task(asyncio.to_thread(_run, entries, client, stopped),
                               name="fixed-default-cache-warmup")
    def report(done):
        if not done.cancelled() and done.exception() is not None:
            error = done.exception()
            log.error("Fixed default warmup failed", exc_info=(type(error), error, error.__traceback__))
    task.add_done_callback(report)
    return Warmup(task, stopped)


async def stop(handle):
    if handle is None:
        return
    handle.stop_event.set()
    # Shield actual SQL cleanup; cancellation must not orphan the worker thread.
    while not handle.task.done():
        try:
            await asyncio.shield(handle.task)
        except asyncio.CancelledError:
            continue
        except Exception:
            break
    await asyncio.gather(handle.task, return_exceptions=True)
