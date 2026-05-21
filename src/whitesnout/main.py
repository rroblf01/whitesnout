from __future__ import annotations

from whitesnout.config import Config


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

        if self.config.app is not None:
            await self.config.app(scope, receive, send)
