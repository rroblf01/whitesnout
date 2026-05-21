from __future__ import annotations

import os
from collections.abc import Callable
from contextlib import suppress

ENV_PREFIX = "WHITESNOUT_"


def _bool(val: str) -> bool:
    return val.lower().strip() in ("true", "1", "yes")


def _str_list(val: str) -> list[str]:
    return [s.strip() for s in val.split(",") if s.strip()]


def _str_set(val: str) -> set[str]:
    return {s.strip() for s in val.split(",") if s.strip()}


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
    "cors_allow_origins": _str_list,
    "hsts": str,
    "csp": str,
    "referrer_policy": str,
    "permissions_policy": str,
    "force_text_extensions": _str_set,
    "skip_compress_extensions": _str_set,
    "manifest_path": str,
    "autocompress": _bool,
    "autocompress_max_size": int,
    "autorefresh": _bool,
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
        "cors_allow_origins",
        "hsts",
        "csp",
        "referrer_policy",
        "permissions_policy",
        "mime_types",
        "force_text_extensions",
        "skip_compress_extensions",
        "manifest_path",
        "autocompress",
        "autocompress_max_size",
        "on_request",
        "autorefresh",
        "path_resolver",
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
        cors_allow_origins: list[str] | None = None,
        hsts: str | None = None,
        csp: str | None = None,
        referrer_policy: str | None = None,
        permissions_policy: str | None = None,
        mime_types: dict[str, str] | None = None,
        force_text_extensions: set[str] | None = None,
        skip_compress_extensions: set[str] | None = None,
        manifest_path: str | None = None,
        autocompress: bool | None = None,
        autocompress_max_size: int | None = None,
        on_request: Callable | None = None,
        autorefresh: bool | None = None,
        path_resolver: Callable | None = None,
    ) -> None:
        env = _read_env()

        self.directory = (
            directory if directory is not None else env.get("directory", "static")
        )
        self.index_file = (
            index_file
            if index_file is not None
            else env.get("index_file", "index.html")
        )
        self.cache_max_age = (
            cache_max_age
            if cache_max_age is not None
            else env.get("cache_max_age", 3600)
        )
        self.immutable_max_age = (
            immutable_max_age
            if immutable_max_age is not None
            else env.get("immutable_max_age", 31536000)
        )
        self.immutable_pattern = (
            immutable_pattern
            if immutable_pattern is not None
            else env.get("immutable_pattern", r"\.[a-f0-9]{8,}\.")
        )
        self.chunk_size = (
            chunk_size if chunk_size is not None else env.get("chunk_size", 65536)
        )
        self.charset = charset if charset is not None else env.get("charset", "utf-8")
        self.brotli = brotli if brotli is not None else env.get("brotli", True)
        self.gzip = gzip if gzip is not None else env.get("gzip", True)
        self.max_cache_size = (
            max_cache_size
            if max_cache_size is not None
            else env.get("max_cache_size", 64)
        )
        self.security_headers = (
            security_headers
            if security_headers is not None
            else env.get("security_headers", True)
        )
        self.cors = cors if cors is not None else env.get("cors", False)
        self.error_responses = (
            error_responses
            if error_responses is not None
            else {
                404: b"Not Found",
                405: b"Method Not Allowed",
                416: b"Range Not Satisfiable",
            }
        )
        self.log_level = log_level
        self.sync_threshold = (
            sync_threshold
            if sync_threshold is not None
            else env.get("sync_threshold", 65536)
        )

        # CORS allowlist: explicit list > legacy cors=True (*) > None
        if cors_allow_origins is not None:
            self.cors_allow_origins = cors_allow_origins
        elif "cors_allow_origins" in env:
            self.cors_allow_origins = env["cors_allow_origins"]
        elif self.cors:
            self.cors_allow_origins = ["*"]
        else:
            self.cors_allow_origins = []

        self.hsts = hsts if hsts is not None else env.get("hsts")
        self.csp = csp if csp is not None else env.get("csp")
        self.referrer_policy = (
            referrer_policy
            if referrer_policy is not None
            else env.get("referrer_policy")
        )
        self.permissions_policy = (
            permissions_policy
            if permissions_policy is not None
            else env.get("permissions_policy")
        )
        self.mime_types = mime_types if mime_types is not None else {}
        self.force_text_extensions = (
            force_text_extensions
            if force_text_extensions is not None
            else env.get("force_text_extensions", set())
        )
        self.skip_compress_extensions = (
            skip_compress_extensions
            if skip_compress_extensions is not None
            else env.get(
                "skip_compress_extensions",
                {
                    ".jpg",
                    ".jpeg",
                    ".png",
                    ".gif",
                    ".webp",
                    ".woff",
                    ".woff2",
                    ".gz",
                    ".br",
                    ".zip",
                },
            )
        )
        self.manifest_path = (
            manifest_path if manifest_path is not None else env.get("manifest_path")
        )
        self.autocompress = (
            autocompress if autocompress is not None else env.get("autocompress", False)
        )
        self.autocompress_max_size = (
            autocompress_max_size
            if autocompress_max_size is not None
            else env.get("autocompress_max_size", 1_048_576)
        )
        self.on_request = on_request
        self.autorefresh = (
            autorefresh if autorefresh is not None else env.get("autorefresh", False)
        )
        self.path_resolver = path_resolver
