from __future__ import annotations

from collections import OrderedDict
from typing import Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")

_RUST_AVAILABLE = False

try:
    from whitesnout._rs import LRUCache as _RustLRUCache  # type: ignore[no-redef]

    _RUST_AVAILABLE = True
except ImportError:
    _RustLRUCache = None  # type: ignore[assignment]


class LRUCache(Generic[K, V]):
    __slots__ = ("_impl",)

    def __init__(self, maxsize: int = 100) -> None:
        if _RUST_AVAILABLE:
            self._impl: _PyLRUCache | _RustLRUCache = _RustLRUCache(maxsize)
        else:
            self._impl = _PyLRUCache(maxsize)

    def get(self, key: K) -> V | None:
        return self._impl.get(key)  # type: ignore[return-value]

    def put(self, key: K, value: V) -> None:
        self._impl.put(key, value)  # type: ignore[arg-type]

    def clear(self) -> None:
        self._impl.clear()


class _PyLRUCache(Generic[K, V]):
    __slots__ = ("_maxsize", "_data")

    def __init__(self, maxsize: int = 100) -> None:
        self._maxsize = maxsize
        self._data: OrderedDict[K, V] = OrderedDict()

    def get(self, key: K) -> V | None:
        if key not in self._data:
            return None
        self._data.move_to_end(key)
        return self._data[key]

    def put(self, key: K, value: V) -> None:
        self._data[key] = value
        self._data.move_to_end(key)
        if len(self._data) > self._maxsize:
            self._data.popitem(last=False)

    def clear(self) -> None:
        self._data.clear()
