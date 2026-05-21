from __future__ import annotations

import re


class Config:
    __slots__ = (
        "directory",
        "app",
        "index_file",
        "cache_max_age",
        "immutable_max_age",
        "immutable_pattern",
        "chunk_size",
        "charset",
        "brotli",
        "gzip",
        "max_cache_size",
    )

    def __init__(
        self,
        *,
        directory: str = "static",
        app: object | None = None,
        index_file: str = "index.html",
        cache_max_age: int = 3600,
        immutable_max_age: int = 31536000,
        immutable_pattern: str = r"\.[a-f0-9]{8,}\.",
        chunk_size: int = 65536,
        charset: str = "utf-8",
        brotli: bool = True,
        gzip: bool = True,
        max_cache_size: int = 100,
    ) -> None:
        self.directory = directory
        self.app = app
        self.index_file = index_file
        self.cache_max_age = cache_max_age
        self.immutable_max_age = immutable_max_age
        self.immutable_pattern = re.compile(immutable_pattern)
        self.chunk_size = chunk_size
        self.charset = charset
        self.brotli = brotli
        self.gzip = gzip
        self.max_cache_size = max_cache_size
