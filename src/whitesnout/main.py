from __future__ import annotations

from whitesnout.config import Config
from whitesnout.file_handler import sanitize_path
from whitesnout.response import (
    build_headers,
    iter_chunks,
    not_found_headers,
    send_response,
)
from whitesnout.utils import guess_content_type


class WhiteSnout:
    __slots__ = ("config",)

    def __init__(
        self,
        app: object | None = None,
        *,
        directory: str = "static",
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
        )

    async def __call__(
        self,
        scope: dict,
        receive: object,
        send: object,
    ) -> None:
        if scope["type"] != "http":
            app = self.config.app
            if app is not None:
                await app(scope, receive, send)
            return

        if scope["method"] not in ("GET", "HEAD"):
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

        path = scope["path"].split("?")[0]
        file_path = sanitize_path(self.config.directory, path)

        if file_path is None:
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

        st = file_path.stat()
        extra_headers: list[tuple[bytes, bytes]] = []

        content_type = guess_content_type(str(file_path), self.config.charset)
        headers = build_headers(
            content_type=content_type,
            content_length=st.st_size,
            status=200,
            extra=extra_headers,
        )

        if scope["method"] == "HEAD":
            await send_response(send, 200, headers)
            return

        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": headers,
        })

        async for chunk in iter_chunks(file_path, self.config.chunk_size):
            await send({
                "type": "http.response.body",
                "body": chunk,
                "more_body": True,
            })
        await send({
            "type": "http.response.body",
            "body": b"",
            "more_body": False,
        })
