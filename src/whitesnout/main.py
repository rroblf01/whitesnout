from __future__ import annotations

import logging
import os
import time

from whitesnout.cache import LRUCache
from whitesnout.config import Config
from whitesnout.file_handler import (
    find_compressed,
    resolve_directory,
    resolve_index,
    sanitize_path,
)
from whitesnout.response import (
    build_cache_control,
    build_content_range,
    build_headers,
    check_304,
    compute_etag,
    format_last_modified,
    iter_chunks,
    not_found_headers,
    parse_range,
    redirect_headers,
    security_headers,
    send_response,
)
from whitesnout.types import ASGIApp, ASGIReceive, ASGISend
from whitesnout.utils import guess_content_type

logger = logging.getLogger("whitesnout")


def _get_accept_encoding(scope: dict) -> str:
    for name, value in scope.get("headers", []):
        if name.lower() == b"accept-encoding":
            return value.decode()
    return ""


def _cors_headers() -> list[tuple[bytes, bytes]]:
    return [(b"access-control-allow-origin", b"*")]


class WhiteSnout:
    __slots__ = ("config", "_stat_cache")

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
        )
        self._stat_cache: LRUCache[str, os.stat_result] = LRUCache(
            maxsize=max_cache_size if max_cache_size is not None else 100
        )

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
                from whitesnout.response import method_not_allowed_headers

                await send_response(
                    send,
                    405,
                    method_not_allowed_headers(),
                    b"Method Not Allowed",
                )
            return

        # CORS preflight
        if scope["method"] == "OPTIONS":
            if self.config.cors:
                extra = _cors_headers()
            else:
                await send_response(
                    send,
                    405,
                    not_found_headers(),
                    b"Method Not Allowed",
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
        file_path = sanitize_path(self.config.directory, path)

        if file_path is None:
            dir_path = resolve_directory(self.config.directory, path)
            if dir_path is not None:
                if not path.endswith("/"):
                    redirect_to = path + "/"
                    qs = scope.get("query_string", b"")
                    if qs:
                        redirect_to += "?" + qs.decode()
                    await send_response(
                        send,
                        301,
                        redirect_headers(redirect_to),
                        b"Moved Permanently",
                    )
                    return
                index = resolve_index(dir_path, self.config.index_file)
                if index is not None:
                    file_path = index
                else:
                    if self.config.app is not None:
                        await self.config.app(scope, receive, send)
                    else:
                        await send_response(
                            send,
                            404,
                            not_found_headers(),
                            b"Not Found",
                        )
                    return
            else:
                if self.config.app is not None:
                    await self.config.app(scope, receive, send)
                else:
                    await send_response(
                        send,
                        404,
                        not_found_headers(),
                        b"Not Found",
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
        st = self._stat_cache.get(cache_key)
        if st is None:
            st = serve_path.stat()
            self._stat_cache.put(cache_key, st)

        file_size = st.st_size
        etag = compute_etag(st)
        last_modified = format_last_modified(st)
        cache_control = build_cache_control(self.config, file_path.name)

        # Parse Range header
        range_header = None
        for name, value in scope.get("headers", []):
            if name.lower() == b"range":
                range_header = value.decode()
                break

        range_spec: tuple[int, int] | None = None
        if range_header and scope["method"] == "GET":
            range_spec = parse_range(range_header, file_size)
            if range_spec is None:
                sec = security_headers(self.config.security_headers)
                cors = _cors_headers() if self.config.cors else []
                await send_response(
                    send,
                    416,
                    [
                        (b"content-range", f"bytes */{file_size}".encode()),
                        (b"content-type", b"text/plain; charset=utf-8"),
                        *sec,
                        *cors,
                    ],
                    b"Range Not Satisfiable",
                )
                return

        if check_304(scope.get("headers", []), etag, last_modified):
            sec = security_headers(self.config.security_headers)
            cors = _cors_headers() if self.config.cors else []
            await send_response(
                send,
                304,
                [
                    (b"etag", etag.encode()),
                    (b"last-modified", last_modified.encode()),
                    (b"cache-control", cache_control.encode()),
                    *sec,
                    *cors,
                ],
            )
            return

        extra_headers: list[tuple[bytes, bytes]] = [
            (b"etag", etag.encode()),
            (b"last-modified", last_modified.encode()),
            (b"cache-control", cache_control.encode()),
        ]
        extra_headers.extend(security_headers(self.config.security_headers))
        if self.config.cors:
            extra_headers.extend(_cors_headers())

        if content_encoding:
            extra_headers.append((b"content-encoding", content_encoding.encode()))

        status = 206 if range_spec else 200
        content_length = file_size

        if range_spec:
            rstart, rend = range_spec
            content_length = rend - rstart + 1
            extra_headers.append(
                (b"content-range", build_content_range(rstart, rend, file_size))
            )

        content_type = guess_content_type(str(file_path), self.config.charset)
        headers = build_headers(
            content_type=content_type,
            content_length=content_length,
            extra=extra_headers,
        )

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

        if range_spec:
            rstart, rend = range_spec
            async for chunk in iter_chunks(
                serve_path, self.config.chunk_size, start=rstart, end=rend
            ):
                await send(
                    {
                        "type": "http.response.body",
                        "body": chunk,
                        "more_body": True,
                    }
                )
        else:
            async for chunk in iter_chunks(serve_path, self.config.chunk_size):
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

        elapsed = time.perf_counter() - t0
        logger.info(
            "%s %s %s %s %.1fms",
            scope["method"],
            path,
            status,
            content_length,
            elapsed * 1000,
        )
