"""One nonblocking user-write slot per existing worker process."""
from contextlib import contextmanager
from threading import BoundedSemaphore

from fastapi import HTTPException

_WRITE_SLOT = BoundedSemaphore(1)


@contextmanager
def write_gate():
    if not _WRITE_SLOT.acquire(blocking=False):
        raise HTTPException(429, detail={'code': 'write_capacity_exceeded', 'message': '写入繁忙，请稍后重试'}, headers={'Retry-After': '1'})
    try:
        yield
    finally:
        _WRITE_SLOT.release()
