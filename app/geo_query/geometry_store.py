from __future__ import annotations

from pathlib import Path
from threading import Lock


class GeometryStore:
    def __init__(self, path: Path):
        self.path = path
        self._fp = None
        self._read_lock = Lock()

    def _ensure_open(self):
        if self._fp is None or self._fp.closed:
            self._fp = self.path.open("rb")
        return self._fp

    def read(self, offset: int, length: int) -> bytes:
        with self._read_lock:
            f = self._ensure_open()
            f.seek(offset)
            return f.read(length)

    def close(self) -> None:
        with self._read_lock:
            if self._fp is not None and not self._fp.closed:
                self._fp.close()
