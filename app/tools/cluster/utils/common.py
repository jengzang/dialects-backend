"""
Cluster shared low-level helpers.
"""

from __future__ import annotations

import time
from typing import Any, Iterable, List, Optional, Sequence


def quote_identifier(name: str) -> str:
    safe_name = name.replace('"', '""')
    return f'"{safe_name}"'


def now_ms() -> int:
    return int(time.time() * 1000)


def dedupe(items: Iterable[str]) -> List[str]:
    return list(dict.fromkeys(item for item in items if item))


def safe_text(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def chunked(items: Sequence[str], size: int):
    for index in range(0, len(items), size):
        yield items[index:index + size]
