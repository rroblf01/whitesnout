from __future__ import annotations

import pytest

from whitesnout.file_handler import clear_compressed_cache
from whitesnout.types import ASGIApp


@pytest.fixture(autouse=True)
def _clear_compressed_cache() -> None:
    clear_compressed_cache()


class ASGITestClient:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def get(
        self, path: str, headers: list[tuple[bytes, bytes]] | None = None
    ) -> dict:
        scope: dict = {
            "type": "http",
            "method": "GET",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": headers or [],
            "http_version": "1.1",
            "scheme": "http",
            "client": ("127.0.0.1", 50000),
            "server": ("127.0.0.1", 8000),
        }
        body_chunks: list[bytes] = []
        response_start: dict = {}

        async def receive() -> dict:
            return {"type": "http.disconnect"}

        async def send(event: dict) -> None:
            nonlocal response_start
            if event["type"] == "http.response.start":
                response_start = event
            elif event["type"] == "http.response.body":
                if event.get("body"):
                    body_chunks.append(event["body"])
                if not event.get("more_body", False):
                    pass

        await self.app(scope, receive, send)
        body = b"".join(body_chunks)
        return {
            "status": response_start.get("status", 500),
            "headers": dict(response_start.get("headers", [])),
            "body": body,
        }


def read_test_file(path: str) -> bytes:
    from pathlib import Path

    return (Path(__file__).parent / path).read_bytes()
