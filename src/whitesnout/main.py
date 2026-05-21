from __future__ import annotations

import logging
import time
from pathlib import Path

from whitesnout.cache import StatCache
from whitesnout.config import Config
from whitesnout.file_handler import (
    find_compressed,
    resolve_directory,
    resolve_index,
    sanitize_path,
)
from whitesnout.response import (
    build_full_response,
    build_headers,
    error_headers,
    iter_chunks,
    redirect_headers,
    send_response,
)
from whitesnout.types import ASGIApp, ASGIReceive, ASGISend

logger = logging.getLogger("whitesnout")


def _get_accept_encoding(scope: dict) -> str:
    for name, value in scope.get("headers", []):
        if name.lower() == b"accept-encoding":
            return value.decode()
    return ""


def _cors_headers() -> list[tuple[bytes, bytes]]:
    return [(b"access-control-allow-origin", b"*")]


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
        "_stat_cache",
        "_extra_files",
        "_extra_dirs",
        "_log_handler",
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
    ) -> None:
        self.config = Config(
            directory=directory,
            app=app,
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
        )
        self._stat_cache: StatCache = StatCache(
            maxsize=max_cache_size if max_cache_size is not None else 100
        )
        self._extra_files: dict[str, Path] = {}
        self._extra_dirs: list[tuple[str, Path]] = []
        self._log_handler: logging.Handler | None = None
        self._setup_logging()

    def _setup_logging(self) -> None:
        if self.config.log_level is None:
            logger.handlers.clear()
            logger.addHandler(logging.NullHandler())
            logger.setLevel(logging.CRITICAL + 1)
        else:
            logger.handlers.clear()
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
        for path, file_path in files.items():
            self._extra_files[path] = Path(file_path)

    def remove_files(self, *paths: str) -> None:
        """Remove previously registered extra files."""
        for path in paths:
            self._extra_files.pop(path, None)

    def add_directory(self, prefix: str, directory: str | Path) -> None:
        """Serve an additional directory under a URL prefix.

        Example:
            app.add_directory("/media", "/mnt/media")
            # GET /media/video.mp4 -> /mnt/media/video.mp4
        """
        self._extra_dirs.append((prefix, Path(directory)))

    def remove_directory(self, prefix: str) -> None:
        """Remove a previously registered extra directory."""
        self._extra_dirs = [(p, d) for p, d in self._extra_dirs if p != prefix]

    def invalidate_cache(self) -> None:
        """Purge the stat cache."""
        self._stat_cache.clear()

    async def __call__(
        self,
        scope: dict,
        receive: ASGIReceive,
        send: ASGISend,
    ) -> None:
        t0 = time.perf_counter()

        if scope["type"] != "http":
            app = self.config.app
            if app is not None:
                await app(scope, receive, send)
            return

        if scope["method"] not in ("GET", "HEAD") and scope["method"] != "OPTIONS":
            if self.config.app is not None:
                await self.config.app(scope, receive, send)
            else:
                body = self.config.error_responses.get(405, b"")
                await send_response(
                    send,
                    405,
                    error_headers(405, body, self.config.error_responses),
                    body,
                )
            return

        # CORS preflight
        if scope["method"] == "OPTIONS":
            if self.config.cors:
                extra = _cors_headers()
            else:
                body = self.config.error_responses.get(405, b"")
                await send_response(
                    send,
                    405,
                    error_headers(405, body, self.config.error_responses),
                    body,
                )
                return
            headers = build_headers(
                content_type="text/plain; charset=utf-8",
                content_length=0,
                extra=extra,
            )
            await send_response(send, 204, headers)
            return

        path = scope["path"].split("?")[0]
        file_path = _resolve_requested_path(
            self.config, path, self._extra_files, self._extra_dirs
        )

        if file_path is None:
            dir_path = _resolve_directory_path(self.config, path, self._extra_dirs)
            if dir_path is not None:
                if not path.endswith("/"):
                    redirect_to = path + "/"
                    qs = scope.get("query_string", b"")
                    if qs:
                        redirect_to += "?" + qs.decode()
                    body = self.config.error_responses.get(301, b"")
                    await send_response(
                        send,
                        301,
                        redirect_headers(redirect_to),
                        body,
                    )
                    return
                index = resolve_index(dir_path, self.config.index_file)
                if index is not None:
                    file_path = index
                else:
                    if self.config.app is not None:
                        await self.config.app(scope, receive, send)
                    else:
                        body = self.config.error_responses.get(404, b"")
                        await send_response(
                            send,
                            404,
                            error_headers(404, body, self.config.error_responses),
                            body,
                        )
                    return
            else:
                if self.config.app is not None:
                    await self.config.app(scope, receive, send)
                else:
                    body = self.config.error_responses.get(404, b"")
                    await send_response(
                        send,
                        404,
                        error_headers(404, body, self.config.error_responses),
                        body,
                    )
                return

        accept_encoding = _get_accept_encoding(scope)
        compressed = find_compressed(
            file_path,
            accept_encoding,
            allow_brotli=self.config.brotli,
            allow_gzip=self.config.gzip,
        )

        if compressed is not None:
            serve_path, content_encoding = compressed
        else:
            serve_path = file_path
            content_encoding = None

        cache_key = str(serve_path)
        cached = self._stat_cache.get(cache_key)
        if cached is not None:
            file_size, mtime_ns = cached
        else:
            st = serve_path.stat()
            file_size, mtime_ns = st.st_size, st.st_mtime_ns
            self._stat_cache.put(cache_key, file_size, mtime_ns)

        # Extract relevant headers in a single pass
        range_header: str | None = None
        if_none_match: str | None = None
        if_modified_since: str | None = None
        for name, value in scope.get("headers", []):
            low = name.lower()
            if low == b"range":
                range_header = value.decode()
            elif low == b"if-none-match":
                if_none_match = value.decode()
            elif low == b"if-modified-since":
                if_modified_since = value.decode()

        headers, status, content_length, range_spec, is_304 = build_full_response(
            file_size=file_size,
            mtime_ns=mtime_ns,
            filename=file_path.name,
            charset=self.config.charset,
            cache_max_age=self.config.cache_max_age,
            immutable_max_age=self.config.immutable_max_age,
            immutable_pattern=self.config.immutable_pattern,
            content_encoding=content_encoding,
            security_enabled=self.config.security_headers,
            cors_enabled=self.config.cors,
            range_header=range_header,
            method=scope["method"],
            if_none_match=if_none_match,
            if_modified_since=if_modified_since,
            file_path_str=str(file_path),
        )

        if is_304:
            await send_response(send, 304, headers)
            return

        if status == 416:
            body = self.config.error_responses.get(416, b"")
            await send_response(
                send,
                416,
                [
                    *headers,
                    *error_headers(416, body, self.config.error_responses),
                ],
                body,
            )
            return

        if scope["method"] == "HEAD":
            await send_response(send, status, headers)
            return

        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": headers,
            }
        )

        async for chunk in iter_chunks(
            serve_path,
            self.config.chunk_size,
            start=range_spec[0] if range_spec else 0,
            end=range_spec[1] if range_spec else None,
            sync_threshold=self.config.sync_threshold,
            file_size=file_size,
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

        if self.config.log_level is not None:
            elapsed = time.perf_counter() - t0
            logger.info(
                "%s %s %s %s %.1fms",
                scope["method"],
                path,
                status,
                content_length,
                elapsed * 1000,
            )
