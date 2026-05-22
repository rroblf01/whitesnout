from __future__ import annotations

import asyncio
import inspect
import logging
import time
from collections.abc import Callable
from pathlib import Path

from whitesnout.autocompress import (
    CompressedCache,
    compress_bytes,
    pick_encoding,
    should_autocompress,
)
from whitesnout.cache import LRUCache, StatCache
from whitesnout.config import Config
from whitesnout.file_handler import (
    resolve_directory,
    resolve_index,
    sanitize_path,
)
from whitesnout.manifest import load_manifest
from whitesnout.response import (
    build_headers,
    build_response_pipeline,
    error_headers,
    iter_chunks,
    redirect_headers,
    send_response,
)
from whitesnout.types import ASGIApp, ASGIReceive, ASGISend

logger = logging.getLogger("whitesnout")


def _read_full(path: Path) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def _read_range(path: Path, start: int, length: int) -> bytes:
    with open(path, "rb") as f:
        if start:
            f.seek(start)
        return f.read(length)


def _log_request(method: str, path: str, status: int, length: int, t0: float) -> None:
    if logger.isEnabledFor(logging.INFO):
        logger.info(
            "%s %s %s %s %.1fms",
            method,
            path,
            status,
            length,
            (time.perf_counter() - t0) * 1000,
        )


def _cors_headers() -> list[tuple[bytes, bytes]]:
    return [(b"access-control-allow-origin", b"*")]


def _build_extra_headers(config: Config) -> list[tuple[bytes, bytes]]:
    """Pre-compute config-driven response headers that don't vary per request."""
    extra: list[tuple[bytes, bytes]] = []
    if config.hsts:
        extra.append((b"strict-transport-security", config.hsts.encode()))
    if config.csp:
        extra.append((b"content-security-policy", config.csp.encode()))
    if config.referrer_policy:
        extra.append((b"referrer-policy", config.referrer_policy.encode()))
    if config.permissions_policy:
        extra.append((b"permissions-policy", config.permissions_policy.encode()))
    return extra


def _resolve_cors_origin(
    allow_origins: list[str], request_origin: str | None
) -> bytes | None:
    """Return the Access-Control-Allow-Origin value for this request, or None."""
    if not allow_origins:
        return None
    if "*" in allow_origins and not request_origin:
        return b"*"
    if request_origin is None:
        return None
    if "*" in allow_origins:
        return request_origin.encode()
    if request_origin in allow_origins:
        return request_origin.encode()
    return None


def _patch_content_length(headers: list[tuple[bytes, bytes]], new_length: int) -> None:
    new_val = str(new_length).encode()
    for i, (k, _) in enumerate(headers):
        if k == b"content-length":
            headers[i] = (b"content-length", new_val)
            return


def _override_content_type(
    headers: list[tuple[bytes, bytes]], file_path_str: str, mime_types: dict[str, str]
) -> None:
    """Replace content-type when the user provided a custom MIME for this extension."""
    if not mime_types:
        return
    dot = file_path_str.rfind(".")
    if dot < 0:
        return
    ext = file_path_str[dot:].lower()
    custom = mime_types.get(ext)
    if custom is None:
        return
    for i, (k, _) in enumerate(headers):
        if k == b"content-type":
            headers[i] = (b"content-type", custom.encode())
            return


def _resolve_requested_path(
    config: Config,
    path: str,
    extra_files: dict[str, Path],
    extra_dirs: list[tuple[str, Path]],
) -> Path | None:
    # 1. Check extra_files first
    if path in extra_files:
        fp = extra_files[path]
        if fp.exists() and fp.is_file():
            return fp

    # 2. Check extra_dirs by prefix
    for prefix, root in extra_dirs:
        if path.startswith(prefix):
            sub = path[len(prefix) :]
            return sanitize_path(str(root), sub)

    # 3. Check main directory
    return sanitize_path(config.directory, path)


def _resolve_directory_path(
    config: Config,
    path: str,
    extra_dirs: list[tuple[str, Path]],
) -> Path | None:
    # Check main directory first
    result = resolve_directory(config.directory, path)
    if result is not None:
        return result

    # Check extra_dirs
    for prefix, root in extra_dirs:
        if path.startswith(prefix):
            sub = path[len(prefix) :]
            return resolve_directory(str(root), sub)

    return None


class WhiteSnout:
    __slots__ = (
        "config",
        "_app",
        "_stat_cache",
        "_stat_cache_impl",
        "_path_cache",
        "_extra_files",
        "_extra_dirs",
        "_log_handler",
        "_extra_response_headers",
        "_manifest_paths",
        "_compressed_cache",
        "_on_request",
        "_on_request_is_async",
    )

    def __init__(
        self,
        app: ASGIApp | None = None,
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
        health_check_path: str | None = None,
    ) -> None:
        self.config = Config(
            directory=directory,
            index_file=index_file,
            cache_max_age=cache_max_age,
            immutable_max_age=immutable_max_age,
            immutable_pattern=immutable_pattern,
            chunk_size=chunk_size,
            charset=charset,
            brotli=brotli,
            gzip=gzip,
            max_cache_size=max_cache_size,
            security_headers=security_headers,
            cors=cors,
            error_responses=error_responses,
            log_level=log_level,
            sync_threshold=sync_threshold,
            cors_allow_origins=cors_allow_origins,
            hsts=hsts,
            csp=csp,
            referrer_policy=referrer_policy,
            permissions_policy=permissions_policy,
            mime_types=mime_types,
            force_text_extensions=force_text_extensions,
            skip_compress_extensions=skip_compress_extensions,
            manifest_path=manifest_path,
            autocompress=autocompress,
            autocompress_max_size=autocompress_max_size,
            on_request=on_request,
            autorefresh=autorefresh,
            path_resolver=path_resolver,
            health_check_path=health_check_path,
        )
        self._app = app
        self._stat_cache: StatCache = StatCache(
            maxsize=max_cache_size if max_cache_size is not None else 64
        )
        self._stat_cache_impl = self._stat_cache._impl
        self._path_cache: LRUCache[str, Path | None] = LRUCache(
            maxsize=max_cache_size if max_cache_size is not None else 64
        )
        self._extra_files: dict[str, Path] = {}
        self._extra_dirs: list[tuple[str, Path]] = []
        self._log_handler: logging.Handler | None = None

        self._extra_response_headers = _build_extra_headers(self.config)

        self._manifest_paths: set[str] = (
            load_manifest(self.config.manifest_path)
            if self.config.manifest_path
            else set()
        )

        self._compressed_cache: CompressedCache | None = (
            CompressedCache() if self.config.autocompress else None
        )

        self._on_request = self.config.on_request
        self._on_request_is_async = (
            self._on_request is not None
            and inspect.iscoroutinefunction(self._on_request)
        )

        self._setup_logging()

    def _setup_logging(self) -> None:
        logger.handlers.clear()
        if self.config.log_level is None:
            logger.setLevel(logging.CRITICAL + 1)
        else:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s %(levelname)s %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
            )
            logger.addHandler(handler)
            logger.setLevel(self.config.log_level.upper())

    def add_files(self, files: dict[str, str | Path]) -> None:
        """Register individual files to serve at specific paths.

        Example:
            app.add_files({
                "/.well-known/security.txt": Path("security/security.txt"),
                "/favicon.ico": "branding/favicon.ico",
            })
        """
        self._path_cache.clear()
        for path, file_path in files.items():
            self._extra_files[path] = Path(file_path)

    def remove_files(self, *paths: str) -> None:
        """Remove previously registered extra files."""
        self._path_cache.clear()
        for path in paths:
            self._extra_files.pop(path, None)

    def add_directory(self, prefix: str, directory: str | Path) -> None:
        """Serve an additional directory under a URL prefix.

        Example:
            app.add_directory("/media", "/mnt/media")
            # GET /media/video.mp4 -> /mnt/media/video.mp4
        """
        self._path_cache.clear()
        self._extra_dirs.append((prefix, Path(directory)))

    def remove_directory(self, prefix: str) -> None:
        """Remove a previously registered extra directory."""
        self._path_cache.clear()
        self._extra_dirs = [(p, d) for p, d in self._extra_dirs if p != prefix]

    def invalidate_cache(self) -> None:
        """Purge all caches."""
        self._stat_cache.clear()
        self._path_cache.clear()

    async def __call__(
        self,
        scope: dict,
        receive: ASGIReceive,
        send: ASGISend,
    ) -> None:
        config = self.config
        log_enabled = config.log_level is not None
        t0 = time.perf_counter() if log_enabled else 0.0

        if scope["type"] != "http":
            app = self._app
            if app is not None:
                await app(scope, receive, send)
                return
            if scope["type"] == "lifespan":
                await self._handle_lifespan(receive, send)
            return

        method = scope["method"]
        if method not in ("GET", "HEAD") and method != "OPTIONS":
            if self._app is not None:
                await self._app(scope, receive, send)
            else:
                body = config.error_responses.get(405, b"")
                await send_response(
                    send,
                    405,
                    error_headers(405, body, config.error_responses),
                    body,
                )
            return

        # Extract request Origin (used for CORS allowlist) + relevant headers
        request_origin: str | None = None

        # CORS preflight
        if method == "OPTIONS":
            for name, value in scope.get("headers", []):
                if name.lower() == b"origin":
                    request_origin = value.decode()
                    break
            allowed = _resolve_cors_origin(config.cors_allow_origins, request_origin)
            if allowed is None:
                body = config.error_responses.get(405, b"")
                await send_response(
                    send,
                    405,
                    error_headers(405, body, config.error_responses),
                    body,
                )
                return
            extra = [(b"access-control-allow-origin", allowed)]
            if "*" not in config.cors_allow_origins:
                extra.append((b"vary", b"Origin"))
            headers = build_headers(
                content_type="text/plain; charset=utf-8",
                content_length=0,
                extra=extra,
            )
            await send_response(send, 204, headers)
            return

        path = scope["path"]

        if config.health_check_path and path == config.health_check_path:
            await send_response(
                send,
                200,
                [
                    (b"content-type", b"text/plain; charset=utf-8"),
                    (b"content-length", b"2"),
                    (b"cache-control", b"no-store"),
                ],
                b"OK",
            )
            if log_enabled:
                _log_request(method, path, 200, 2, t0)
            await self._notify_request(scope, 200, 2, t0)
            return

        # Autorefresh: nuke caches so a moved/edited file is picked up on the
        # next request. Cheap (HashMap clear); intended for dev only.
        if config.autorefresh:
            self._path_cache.clear()
            self._stat_cache.clear()

        cached = self._path_cache.get(path)
        if cached is not None:
            file_path = cached
        else:
            file_path = _resolve_requested_path(
                config, path, self._extra_files, self._extra_dirs
            )
            if file_path is None and config.path_resolver is not None:
                file_path = await asyncio.to_thread(config.path_resolver, path)
            if not config.autorefresh:
                self._path_cache.put(path, file_path)

        if file_path is None:
            dir_path = _resolve_directory_path(config, path, self._extra_dirs)
            if dir_path is not None:
                if not path.endswith("/"):
                    redirect_to = path + "/"
                    qs = scope.get("query_string", b"")
                    if qs:
                        redirect_to += "?" + qs.decode()
                    body = config.error_responses.get(301, b"")
                    await send_response(
                        send,
                        301,
                        redirect_headers(redirect_to),
                        body,
                    )
                    return
                index = resolve_index(dir_path, config.index_file)
                if index is not None:
                    file_path = index
                else:
                    if self._app is not None:
                        await self._app(scope, receive, send)
                    else:
                        body = config.error_responses.get(404, b"")
                        await send_response(
                            send,
                            404,
                            error_headers(404, body, config.error_responses),
                            body,
                        )
                    return
            else:
                if self._app is not None:
                    await self._app(scope, receive, send)
                else:
                    body = config.error_responses.get(404, b"")
                    await send_response(
                        send,
                        404,
                        error_headers(404, body, config.error_responses),
                        body,
                    )
                return

        # Extract relevant headers in a single pass
        range_header: str | None = None
        if_none_match: str | None = None
        if_modified_since: str | None = None
        accept_encoding = ""
        need_origin = bool(config.cors_allow_origins)
        for name, value in scope.get("headers", []):
            low = name.lower()
            if low == b"range":
                range_header = value.decode()
            elif low == b"if-none-match":
                if_none_match = value.decode()
            elif low == b"if-modified-since":
                if_modified_since = value.decode()
            elif low == b"accept-encoding":
                accept_encoding = value.decode()
            elif need_origin and low == b"origin":
                request_origin = value.decode()

        is_hashed_override: bool | None = (
            True if self._manifest_paths and path in self._manifest_paths else None
        )

        (
            serve_path,
            headers,
            status,
            content_length,
            range_spec,
            is_304,
            content_encoding,
        ) = build_response_pipeline(
            file_path,
            self._stat_cache_impl,
            accept_encoding,
            allow_brotli=config.brotli,
            allow_gzip=config.gzip,
            filename=file_path.name,
            charset=config.charset,
            cache_max_age=config.cache_max_age,
            immutable_max_age=config.immutable_max_age,
            immutable_pattern=config.immutable_pattern,
            security_enabled=config.security_headers,
            cors_enabled=False,  # CORS handled in Python post-process
            range_header=range_header,
            method=method,
            if_none_match=if_none_match,
            if_modified_since=if_modified_since,
            is_hashed_override=is_hashed_override,
            add_vary=config.brotli or config.gzip,
        )

        # Post-process: extra security headers, CORS allowlist, MIME override
        if self._extra_response_headers:
            headers.extend(self._extra_response_headers)

        if config.cors_allow_origins:
            allowed = _resolve_cors_origin(config.cors_allow_origins, request_origin)
            if allowed is not None:
                headers.append((b"access-control-allow-origin", allowed))
                if "*" not in config.cors_allow_origins:
                    headers.append((b"vary", b"Origin"))

        if config.mime_types:
            _override_content_type(headers, str(file_path), config.mime_types)

        if is_304:
            await send_response(send, 304, headers)
            if self._on_request is not None:
                await self._notify_request(scope, 304, 0, t0)
            if log_enabled:
                _log_request(method, path, 304, 0, t0)
            return

        if status == 416:
            body = config.error_responses.get(416, b"")
            await send_response(
                send,
                416,
                [
                    *headers,
                    *error_headers(416, body, config.error_responses),
                ],
                body,
            )
            if self._on_request is not None:
                await self._notify_request(scope, 416, len(body), t0)
            if log_enabled:
                _log_request(method, path, 416, len(body), t0)
            return

        if method == "HEAD":
            await send_response(send, status, headers)
            if self._on_request is not None:
                await self._notify_request(scope, status, content_length, t0)
            if log_enabled:
                _log_request(method, path, status, content_length, t0)
            return

        # Autocompress: serve a freshly compressed in-memory copy when no
        # pre-compressed variant exists on disk and the file is suitable.
        if (
            self._compressed_cache is not None
            and content_encoding is None
            and range_spec is None
            and content_length <= config.autocompress_max_size
            and should_autocompress(file_path, config.skip_compress_extensions)
        ):
            encoding = pick_encoding(accept_encoding, config.brotli, config.gzip)
            if encoding is not None:
                compressed_body = await self._get_compressed(
                    file_path, encoding, content_length
                )
                if compressed_body is not None:
                    _patch_content_length(headers, len(compressed_body))
                    headers.append((b"content-encoding", encoding.encode()))
                    await send(
                        {
                            "type": "http.response.start",
                            "status": status,
                            "headers": headers,
                        }
                    )
                    await send(
                        {
                            "type": "http.response.body",
                            "body": compressed_body,
                            "more_body": False,
                        }
                    )
                    if self._on_request is not None:
                        await self._notify_request(
                            scope, status, len(compressed_body), t0
                        )
                    if log_enabled:
                        _log_request(method, path, status, len(compressed_body), t0)
                    return

        # Fast path: small file fits in one read, single send pair
        if content_length <= config.sync_threshold:
            if range_spec is not None:
                rstart, rend = range_spec
                body = await asyncio.to_thread(
                    _read_range, serve_path, rstart, rend - rstart + 1
                )
            else:
                body = await asyncio.to_thread(_read_full, serve_path)
            await send(
                {
                    "type": "http.response.start",
                    "status": status,
                    "headers": headers,
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": body,
                    "more_body": False,
                }
            )
            if self._on_request is not None:
                await self._notify_request(scope, status, content_length, t0)
            if log_enabled:
                _log_request(method, path, status, content_length, t0)
            return

        # Streaming path for large files
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": headers,
            }
        )

        async for chunk in iter_chunks(
            serve_path,
            config.chunk_size,
            start=range_spec[0] if range_spec else 0,
            end=range_spec[1] if range_spec else None,
            sync_threshold=config.sync_threshold,
            file_size=content_length,
        ):
            await send(
                {
                    "type": "http.response.body",
                    "body": chunk,
                    "more_body": True,
                }
            )
        await send(
            {
                "type": "http.response.body",
                "body": b"",
                "more_body": False,
            }
        )

        if self._on_request is not None:
            await self._notify_request(scope, status, content_length, t0)
        if log_enabled:
            _log_request(method, path, status, content_length, t0)

    async def _handle_lifespan(self, receive: ASGIReceive, send: ASGISend) -> None:
        while True:
            message = await receive()
            mtype = message["type"]
            if mtype == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif mtype == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return
            else:
                return

    async def _notify_request(
        self, scope: dict, status: int, length: int, t0: float
    ) -> None:
        if self._on_request is None:
            return
        elapsed = time.perf_counter() - t0
        info = {
            "method": scope["method"],
            "path": scope["path"],
            "status": status,
            "length": length,
            "elapsed_s": elapsed,
            "scope": scope,
        }
        try:
            if self._on_request_is_async:
                await self._on_request(info)
            else:
                self._on_request(info)
        except Exception:
            logger.exception("on_request hook raised")

    async def _get_compressed(
        self, file_path: Path, encoding: str, content_length: int
    ) -> bytes | None:
        assert self._compressed_cache is not None
        path_str = str(file_path)
        cached = self._stat_cache_impl.get(path_str)
        if cached is None:
            return None
        _file_size, mtime_ns = cached
        cached_bytes = self._compressed_cache.get(path_str, mtime_ns, encoding)
        if cached_bytes is not None:
            return cached_bytes
        raw = await asyncio.to_thread(_read_full, file_path)
        compressed = await asyncio.to_thread(compress_bytes, raw, encoding)
        if compressed is None or len(compressed) >= content_length:
            # If compression didn't shrink, skip compression for this file
            return None
        self._compressed_cache.put(path_str, mtime_ns, encoding, compressed)
        return compressed
