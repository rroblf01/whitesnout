from __future__ import annotations

import gzip
from collections import OrderedDict
from pathlib import Path
from threading import Lock

_DEFAULT_CACHE_MAX = 128


class CompressedCache:
    """In-memory LRU cache of compressed bytes for on-the-fly compression.

    Each entry: key = (source_path_str, mtime_ns, encoding) -> bytes.
    Bounded by max_entries to cap memory.
    """

    __slots__ = ("_data", "_max", "_lock")

    def __init__(self, max_entries: int = _DEFAULT_CACHE_MAX) -> None:
        self._data: OrderedDict[tuple[str, int, str], bytes] = OrderedDict()
        self._max = max_entries
        self._lock = Lock()

    def get(self, path_str: str, mtime_ns: int, encoding: str) -> bytes | None:
        key = (path_str, mtime_ns, encoding)
        with self._lock:
            if key not in self._data:
                return None
            self._data.move_to_end(key)
            return self._data[key]

    def put(self, path_str: str, mtime_ns: int, encoding: str, data: bytes) -> None:
        key = (path_str, mtime_ns, encoding)
        with self._lock:
            self._data[key] = data
            self._data.move_to_end(key)
            while len(self._data) > self._max:
                self._data.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


_brotli = None
_brotli_checked = False


def _get_brotli():
    global _brotli, _brotli_checked
    if not _brotli_checked:
        _brotli_checked = True
        try:
            import brotli as _br  # type: ignore[import-not-found]

            _brotli = _br
        except ImportError:
            _brotli = None
    return _brotli


def compress_bytes(data: bytes, encoding: str) -> bytes | None:
    """Compress data with the requested encoding. Returns None if encoding
    is unsupported (e.g. brotli when the `brotli` package is missing).
    """
    if encoding == "gzip":
        return gzip.compress(data, compresslevel=6)
    if encoding == "br":
        br = _get_brotli()
        if br is None:
            return None
        return br.compress(data, quality=4)
    return None


def pick_encoding(
    accept_encoding: str, allow_brotli: bool, allow_gzip: bool
) -> str | None:
    """Best encoding offered by the client, preferring brotli."""
    if not accept_encoding:
        return None
    lower = accept_encoding.lower()
    if allow_brotli and "br" in lower and _get_brotli() is not None:
        return "br"
    if allow_gzip and "gzip" in lower:
        return "gzip"
    return None


def should_autocompress(path: Path, skip_extensions: set[str]) -> bool:
    suffix = path.suffix.lower()
    return suffix not in skip_extensions
