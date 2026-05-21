from __future__ import annotations

import gzip

import brotli
import pytest

from whitesnout import WhiteSnout
from whitesnout.utils import guess_content_type


def test_guess_content_type_html() -> None:
    assert guess_content_type("/index.html") == "text/html; charset=utf-8"


def test_guess_content_type_css() -> None:
    assert guess_content_type("/style.css") == "text/css; charset=utf-8"


def test_guess_content_type_js() -> None:
    assert guess_content_type("/app.js") == "application/javascript; charset=utf-8"


def test_guess_content_type_png() -> None:
    assert guess_content_type("/image.png") == "image/png"


def test_guess_content_type_jpg() -> None:
    assert guess_content_type("/photo.jpg") == "image/jpeg"


def test_guess_content_type_svg() -> None:
    assert guess_content_type("/icon.svg") == "image/svg+xml"


def test_guess_content_type_woff2() -> None:
    assert guess_content_type("/font.woff2") == "font/woff2"


def test_guess_content_type_unknown() -> None:
    assert guess_content_type("/file.unknown") == "application/octet-stream"


@pytest.mark.asyncio
async def test_serves_precompressed_gzip() -> None:
    app = WhiteSnout(directory="tests/static")
    original = (await _request(app, "/hello.txt", "")).body
    resp = await _request(app, "/hello.txt", "gzip")
    assert resp.status == 200
    assert resp.headers.get(b"content-encoding") == b"gzip"
    decompressed = gzip.decompress(resp.body)
    assert decompressed == original


@pytest.mark.asyncio
async def test_serves_precompressed_brotli() -> None:
    app = WhiteSnout(directory="tests/static")
    original = (await _request(app, "/hello.txt", "")).body
    resp = await _request(app, "/hello.txt", "br")
    assert resp.status == 200
    assert resp.headers.get(b"content-encoding") == b"br"
    decompressed = brotli.decompress(resp.body)
    assert decompressed == original


@pytest.mark.asyncio
async def test_falls_back_to_original_without_compression() -> None:
    app = WhiteSnout(directory="tests/static")
    resp = await _request(app, "/hello.txt", "")
    assert resp.status == 200
    assert resp.headers.get(b"content-encoding") is None


@pytest.mark.asyncio
async def test_brotli_preferred_over_gzip() -> None:
    app = WhiteSnout(directory="tests/static")
    resp = await _request(app, "/hello.txt", "gzip, br")
    assert resp.status == 200
    assert resp.headers.get(b"content-encoding") in (b"br", b"gzip")


def test_is_hashed_file() -> None:
    from whitesnout.file_handler import is_hashed_file
    assert is_hashed_file("styles.a1b2c3d4.css", r"\.[a-f0-9]{8,}\.")
    assert is_hashed_file("app.12345678.js", r"\.[a-f0-9]{8,}\.")
    assert not is_hashed_file("styles.css", r"\.[a-f0-9]{8,}\.")
    assert not is_hashed_file("index.html", r"\.[a-f0-9]{8,}\.")


def test_build_cache_control() -> None:
    from whitesnout.config import Config
    from whitesnout.response import build_cache_control
    config = Config()
    hashed_cc = build_cache_control(config, "styles.a1b2c3d4.css")
    assert "immutable" in hashed_cc
    assert "max-age=31536000" in hashed_cc

    normal_cc = build_cache_control(config, "styles.css")
    assert "immutable" not in normal_cc
    assert "max-age=3600" in normal_cc


async def _request(app, path: str, accept_encoding: str):
    headers = []
    if accept_encoding:
        headers.append((b"accept-encoding", accept_encoding.encode()))
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": headers,
        "http_version": "1.1",
        "scheme": "http",
        "client": ("127.0.0.1", 50000),
        "server": ("127.0.0.1", 8000),
    }
    response_start = {}
    body_chunks = []

    async def receive():
        return {"type": "http.disconnect"}

    async def send(event):
        nonlocal response_start
        if event["type"] == "http.response.start":
            response_start = event
        elif event["type"] == "http.response.body":
            body_chunks.append(event.get("body", b""))

    await app(scope, receive, send)

    class Resp:
        status: int = response_start.get("status", 500)
        headers: dict = dict(response_start.get("headers", []))
        body: bytes = b"".join(body_chunks)

    return Resp()
