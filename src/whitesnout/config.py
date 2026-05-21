from __future__ import annotations

import os
from contextlib import suppress

ENV_PREFIX = "WHITESNOUT_"


def _bool(val: str) -> bool:
    return val.lower().strip() in ("true", "1", "yes")


_ENV_PARSERS = {
    "directory": str,
    "index_file": str,
    "cache_max_age": int,
    "immutable_max_age": int,
    "immutable_pattern": str,
    "chunk_size": int,
    "charset": str,
    "brotli": _bool,
    "gzip": _bool,
    "max_cache_size": int,
    "security_headers": _bool,
    "cors": _bool,
    "sync_threshold": int,
}


def _read_env() -> dict:
    cfg: dict = {}
    for key, parser in _ENV_PARSERS.items():
        val = os.environ.get(f"{ENV_PREFIX}{key.upper()}")
        if val is not None:
            with suppress(ValueError, TypeError):
                cfg[key] = parser(val)
    return cfg


class Config:
    __slots__ = (
        "directory",
        "index_file",
        "cache_max_age",
        "immutable_max_age",
        "immutable_pattern",
        "chunk_size",
        "charset",
        "brotli",
        "gzip",
        "max_cache_size",
        "security_headers",
        "cors",
        "error_responses",
        "log_level",
        "sync_threshold",
    )

    def __init__(
        self,
        *,
        directory: str | None = None,
        index_file: str | None = None,
        cache_max_age: int | None = None,
        immutable_max_age: int | None = None,
        immutable_pattern: str | None = None,
        chunk_size: int | None = None,
        charset: str | None = None,
        brotli: bool | None = None,
        gzip: bool | None = None,
        max_cache_size: int | None = None,
        security_headers: bool | None = None,
        cors: bool | None = None,
        error_responses: dict[int, bytes] | None = None,
        log_level: str | None = "INFO",
        sync_threshold: int | None = None,
    ) -> None:
        env = _read_env()

        self.directory = (
            directory if directory is not None else env.get("directory", "static")
        )  # type: ignore[assignment]
        self.index_file = (
            index_file
            if index_file is not None
            else env.get("index_file", "index.html")
        )  # type: ignore[assignment]
        self.cache_max_age = (
            cache_max_age
            if cache_max_age is not None
            else env.get("cache_max_age", 3600)
        )  # type: ignore[assignment]
        self.immutable_max_age = (
            immutable_max_age
            if immutable_max_age is not None
            else env.get("immutable_max_age", 31536000)
        )  # type: ignore[assignment]
        self.immutable_pattern = (
            immutable_pattern
            if immutable_pattern is not None
            else env.get("immutable_pattern", r"\.[a-f0-9]{8,}\.")
        )  # type: ignore[assignment]
        self.chunk_size = (
            chunk_size if chunk_size is not None else env.get("chunk_size", 65536)
        )  # type: ignore[assignment]
        self.charset = charset if charset is not None else env.get("charset", "utf-8")  # type: ignore[assignment]
        self.brotli = brotli if brotli is not None else env.get("brotli", True)  # type: ignore[assignment]
        self.gzip = gzip if gzip is not None else env.get("gzip", True)  # type: ignore[assignment]
        self.max_cache_size = (
            max_cache_size
            if max_cache_size is not None
            else env.get("max_cache_size", 64)
        )  # type: ignore[assignment]
        self.security_headers = (
            security_headers
            if security_headers is not None
            else env.get("security_headers", True)
        )  # type: ignore[assignment]
        self.cors = cors if cors is not None else env.get("cors", False)  # type: ignore[assignment]
        self.error_responses = (
            error_responses
            if error_responses is not None
            else {
                404: b"Not Found",
                405: b"Method Not Allowed",
                416: b"Range Not Satisfiable",
            }
        )  # type: ignore[assignment]
        self.log_level = log_level  # type: ignore[assignment]
        self.sync_threshold = (
            sync_threshold
            if sync_threshold is not None
            else env.get("sync_threshold", 65536)
        )  # type: ignore[assignment]
