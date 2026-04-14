"""
cluster 低层公共工具。

这里放的都是无状态、可复用的小函数，用来减少各个 service 里重复的细碎逻辑。
"""

from __future__ import annotations

import time
from typing import Any, Iterable, List, Optional, Sequence


def quote_identifier(name: str) -> str:
    """对 SQLite 标识符做最小安全转义，用于动态拼接列名/表名。"""
    safe_name = name.replace('"', '""')
    return f'"{safe_name}"'


def now_ms() -> int:
    """返回当前 Unix 毫秒时间戳。"""
    return int(time.time() * 1000)


def dedupe(items: Iterable[str]) -> List[str]:
    """按出现顺序去重，常用于地点简称和汉字列表。"""
    return list(dict.fromkeys(item for item in items if item))


def safe_text(value: Any) -> Optional[str]:
    """把任意值安全转成字符串；空值统一折叠成 None。"""
    text = str(value or "").strip()
    return text or None


def chunked(items: Sequence[str], size: int):
    """把序列按固定大小切片，避免 SQL 参数列表过长。"""
    for index in range(0, len(items), size):
        yield items[index:index + size]
