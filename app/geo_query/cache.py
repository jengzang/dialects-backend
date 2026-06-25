from __future__ import annotations

from collections import OrderedDict
from typing import Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")


class LRUCache(Generic[K, V]):
    def __init__(self, max_items: int):
        self.max_items = max(1, max_items)
        self._items: OrderedDict[K, V] = OrderedDict()
        self.hit_count = 0
        self.miss_count = 0
        self.eviction_count = 0

    def get(self, key: K):
        if key not in self._items:
            self.miss_count += 1
            return None
        self._items.move_to_end(key)
        self.hit_count += 1
        return self._items[key]

    def put(self, key: K, value: V) -> None:
        if key in self._items:
            self._items.move_to_end(key)
            self._items[key] = value
            return
        self._items[key] = value
        if len(self._items) > self.max_items:
            self._items.popitem(last=False)
            self.eviction_count += 1

    def __contains__(self, key: K) -> bool:
        return key in self._items

    def __len__(self) -> int:
        return len(self._items)
