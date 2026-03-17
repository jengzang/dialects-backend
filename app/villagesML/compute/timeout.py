"""
Timeout helpers for compute APIs.

The previous implementation relied on process-level signals and timer flags.
This module uses asyncio timeouts around worker threads instead, which is
safe under concurrent requests and works consistently across platforms.
"""

from __future__ import annotations

import asyncio
import functools
import logging
import time
from contextlib import contextmanager
from typing import Any, Callable

logger = logging.getLogger(__name__)


class TimeoutException(Exception):
    """Raised when a computation exceeds the configured timeout."""


async def run_with_timeout(
    func: Callable[..., Any],
    seconds: float,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """
    Run a synchronous function in a worker thread with an asyncio timeout.
    """
    try:
        call = functools.partial(func, *args, **kwargs)
        return await asyncio.wait_for(asyncio.to_thread(call), timeout=seconds)
    except asyncio.TimeoutError as exc:
        raise TimeoutException(f"Computation exceeded {seconds} seconds") from exc


async def timeout_async(coro: Any, seconds: int):
    """
    Timeout wrapper for awaitables/coroutines.
    """
    try:
        return await asyncio.wait_for(coro, timeout=seconds)
    except asyncio.TimeoutError as exc:
        raise TimeoutException(f"Async computation exceeded {seconds} seconds") from exc


@contextmanager
def timeout(seconds: int):
    """
    Backward-compatible soft timeout context manager.

    Note:
    - It does not preempt running CPU work.
    - It raises TimeoutException only after the block returns.
    - Prefer `run_with_timeout` for API request paths.
    """
    start = time.monotonic()
    yield
    elapsed = time.monotonic() - start
    if elapsed > seconds:
        raise TimeoutException(f"Computation exceeded {seconds} seconds")


def with_timeout(seconds: int):
    """
    Backward-compatible decorator based on the soft timeout context manager.
    """

    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs) -> Any:
            with timeout(seconds):
                return func(*args, **kwargs)

        return wrapper

    return decorator


class TimeoutManager:
    """Small utility wrapper kept for compatibility."""

    def __init__(self, default_timeout: int = 5):
        self.default_timeout = default_timeout
        self.timeout_counts: dict[str, int] = {}

    def execute_with_timeout(
        self,
        func: Callable,
        timeout_seconds: int | None = None,
        *args,
        **kwargs,
    ) -> Any:
        timeout_seconds = timeout_seconds or self.default_timeout
        func_name = getattr(func, "__name__", "<anonymous>")
        start = time.monotonic()
        result = func(*args, **kwargs)
        elapsed = time.monotonic() - start
        if elapsed > timeout_seconds:
            self.timeout_counts[func_name] = self.timeout_counts.get(func_name, 0) + 1
            logger.error(
                "Function %s timed out after %.2fs (threshold=%ss, count=%s)",
                func_name,
                elapsed,
                timeout_seconds,
                self.timeout_counts[func_name],
            )
            raise TimeoutException(f"Computation exceeded {timeout_seconds} seconds")
        return result

    def get_timeout_stats(self) -> dict:
        return {
            "default_timeout": self.default_timeout,
            "timeout_counts": self.timeout_counts.copy(),
            "total_timeouts": sum(self.timeout_counts.values()),
        }


timeout_manager = TimeoutManager(default_timeout=5)

