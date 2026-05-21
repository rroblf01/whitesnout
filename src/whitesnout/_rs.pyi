"""Type stubs for the Rust extension `whitesnout._rs`.

Generated to match the PyO3 surface defined in `src/lib.rs`. Update this
file when adding or removing `#[pyfunction]` exports.
"""
from __future__ import annotations

from typing import Optional

class LRUCache:
    def __init__(self, maxsize: int = 100) -> None: ...
    def get(self, key: str) -> object | None: ...
    def put(self, key: str, value: object) -> None: ...
    def clear(self) -> None: ...

class StatCache:
    def __init__(self, maxsize: int = 100) -> None: ...
    def get(self, key: str) -> tuple[int, int] | None: ...
    def put(self, key: str, size: int, mtime_ns: int) -> None: ...
    def clear(self) -> None: ...

def guess_content_type(path: str, charset: str = "utf-8") -> str: ...
def parse_accept_encoding(header: str) -> list[str]: ...
def find_compressed(
    file_path: str,
    accept_encoding: str,
    allow_brotli: bool = True,
    allow_gzip: bool = True,
) -> tuple[str, str] | None: ...
def is_hashed_file(filename: str, pattern: str) -> bool: ...
def clear_compressed_cache() -> None: ...
def compute_etag(size: int, mtime_ns: int) -> str: ...
def format_last_modified(mtime_ns: int) -> str: ...
def build_cache_control(
    is_hashed: bool, max_age: int, immutable_max_age: int
) -> str: ...
def security_headers(enabled: bool = True) -> list[tuple[str, str]]: ...
def build_headers(
    content_type: str,
    content_length: int,
    extra: list[tuple[str, str]],
) -> list[tuple[str, str]]: ...
def parse_range(range_header: str, file_size: int) -> tuple[int, int] | None: ...
def build_content_range(start: int, end: int, total: int) -> str: ...
def check_304(
    if_none_match: Optional[str] = None,
    if_modified_since: Optional[str] = None,
    etag: str = "",
    last_modified: str = "",
) -> bool: ...
def build_all_headers(
    content_type: str,
    content_length: int,
    etag: str,
    last_modified: str,
    cache_control: str,
    content_encoding: Optional[str] = None,
    security_enabled: bool = True,
    cors_enabled: bool = False,
    range_header: Optional[str] = None,
    file_size: int = 0,
) -> tuple[list[tuple[bytes, bytes]], int, int, tuple[int, int] | None]: ...
def build_full_response(
    file_size: int,
    mtime_ns: int,
    filename: str,
    charset: str = "utf-8",
    cache_max_age: int = 3600,
    immutable_max_age: int = 31536000,
    immutable_pattern: str = "",
    content_encoding: Optional[str] = None,
    security_enabled: bool = True,
    cors_enabled: bool = False,
    range_header: Optional[str] = None,
    method: str = "GET",
    if_none_match: Optional[str] = None,
    if_modified_since: Optional[str] = None,
    file_path_str: str = "",
) -> tuple[
    list[tuple[bytes, bytes]], int, int, tuple[int, int] | None, bool
]: ...
def build_full_response_v2(
    file_path: str,
    stat_cache: StatCache,
    accept_encoding: str,
    allow_brotli: bool,
    allow_gzip: bool,
    filename: str,
    charset: str,
    cache_max_age: int,
    immutable_max_age: int,
    immutable_pattern: str,
    security_enabled: bool,
    cors_enabled: bool,
    range_header: Optional[str],
    method: str,
    if_none_match: Optional[str],
    if_modified_since: Optional[str],
    is_hashed_override: Optional[bool] = None,
    add_vary: bool = True,
) -> tuple[
    str,
    list[tuple[bytes, bytes]],
    int,
    int,
    tuple[int, int] | None,
    bool,
    Optional[str],
]: ...
