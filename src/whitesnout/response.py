from __future__ import annotations

import os
from pathlib import Path
from typing import AsyncGenerator


async def iter_chunks(path: Path, chunk_size: int) -> AsyncGenerator[bytes, None]:
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            yield chunk


def build_headers(
    *,
    content_type: str,
    content_length: int,
    status: int = 200,
    extra: list[tuple[bytes, bytes]] | None = None,
) -> list[tuple[bytes, bytes]]:
    headers: list[tuple[bytes, bytes]] = [
        (b"content-type", content_type.encode()),
        (b"content-length", str(content_length).encode()),
    ]
    if extra:
        headers.extend(extra)
    return headers


async def send_response(
    send,
    status: int,
    headers: list[tuple[bytes, bytes]],
    body: bytes = b"",
) -> None:
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": headers,
    })
    await send({
        "type": "http.response.body",
        "body": body,
        "more_body": False,
    })


def not_found_headers() -> list[tuple[bytes, bytes]]:
    return [(b"content-type", b"text/plain; charset=utf-8")]


def method_not_allowed_headers() -> list[tuple[bytes, bytes]]:
    return [(b"content-type", b"text/plain; charset=utf-8")]
