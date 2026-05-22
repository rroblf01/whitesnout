"""Edge case tests: Range, conditional requests, streaming, ASGI scopes."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from tests.conftest import ASGITestClient
from whitesnout import WhiteSnout

# ---------- Range request edge cases ----------


async def test_range_full_file(tmp_path: Path) -> None:
    data = b"x" * 1000
    (tmp_path / "a.bin").write_bytes(data)
    app = WhiteSnout(directory=str(tmp_path))
    client = ASGITestClient(app)
    r = await client.get("/a.bin", headers=[(b"range", b"bytes=0-999")])
    assert r["status"] == 206
    assert r["body"] == data


async def test_range_partial(tmp_path: Path) -> None:
    data = b"abcdefghij"
    (tmp_path / "a.bin").write_bytes(data)
    app = WhiteSnout(directory=str(tmp_path))
    client = ASGITestClient(app)
    r = await client.get("/a.bin", headers=[(b"range", b"bytes=2-5")])
    assert r["status"] == 206
    assert r["body"] == b"cdef"
    assert r["headers"][b"content-range"] == b"bytes 2-5/10"


async def test_range_suffix(tmp_path: Path) -> None:
    data = b"abcdefghij"
    (tmp_path / "a.bin").write_bytes(data)
    app = WhiteSnout(directory=str(tmp_path))
    client = ASGITestClient(app)
    # Last 3 bytes
    r = await client.get("/a.bin", headers=[(b"range", b"bytes=-3")])
    assert r["status"] == 206
    assert r["body"] == b"hij"


async def test_range_open_ended(tmp_path: Path) -> None:
    data = b"abcdefghij"
    (tmp_path / "a.bin").write_bytes(data)
    app = WhiteSnout(directory=str(tmp_path))
    client = ASGITestClient(app)
    r = await client.get("/a.bin", headers=[(b"range", b"bytes=7-")])
    assert r["status"] == 206
    assert r["body"] == b"hij"


async def test_range_invalid_unit_returns_200(tmp_path: Path) -> None:
    (tmp_path / "a.bin").write_bytes(b"abc")
    app = WhiteSnout(directory=str(tmp_path))
    client = ASGITestClient(app)
    r = await client.get("/a.bin", headers=[(b"range", b"items=0-100")])
    # Invalid range unit is ignored; full body served
    assert r["status"] == 200


async def test_range_beyond_eof_returns_416(tmp_path: Path) -> None:
    (tmp_path / "a.bin").write_bytes(b"abc")
    app = WhiteSnout(directory=str(tmp_path))
    client = ASGITestClient(app)
    r = await client.get("/a.bin", headers=[(b"range", b"bytes=100-200")])
    assert r["status"] == 416


async def test_range_start_after_end(tmp_path: Path) -> None:
    (tmp_path / "a.bin").write_bytes(b"abcde")
    app = WhiteSnout(directory=str(tmp_path))
    client = ASGITestClient(app)
    r = await client.get("/a.bin", headers=[(b"range", b"bytes=4-2")])
    assert r["status"] == 416


async def test_range_negative_start(tmp_path: Path) -> None:
    (tmp_path / "a.bin").write_bytes(b"abcde")
    app = WhiteSnout(directory=str(tmp_path))
    client = ASGITestClient(app)
    r = await client.get("/a.bin", headers=[(b"range", b"bytes=-0")])
    # bytes=-0 is invalid by spec; should not crash
    assert r["status"] in (200, 416)


async def test_range_garbage_within_bytes_unit(tmp_path: Path) -> None:
    (tmp_path / "a.bin").write_bytes(b"abcde")
    app = WhiteSnout(directory=str(tmp_path))
    client = ASGITestClient(app)
    r = await client.get("/a.bin", headers=[(b"range", b"bytes=not-a-range")])
    # Garbage *within* the `bytes=` unit is unsatisfiable → 416
    assert r["status"] == 416


async def test_head_with_range(tmp_path: Path) -> None:
    (tmp_path / "a.bin").write_bytes(b"abcde")
    app = WhiteSnout(directory=str(tmp_path))
    scope: dict = {
        "type": "http",
        "method": "HEAD",
        "path": "/a.bin",
        "raw_path": b"/a.bin",
        "query_string": b"",
        "headers": [(b"range", b"bytes=0-2")],
        "http_version": "1.1",
        "scheme": "http",
        "client": ("127.0.0.1", 1),
        "server": ("127.0.0.1", 8000),
    }
    body: list[bytes] = []
    start: dict = {}

    async def receive() -> dict:
        return {"type": "http.disconnect"}

    async def send(event: dict) -> None:
        nonlocal start
        if event["type"] == "http.response.start":
            start = event
        elif event["type"] == "http.response.body" and event.get("body"):
            body.append(event["body"])

    await app(scope, receive, send)
    # HEAD should not return a body, regardless of Range
    assert b"".join(body) == b""


# ---------- Conditional requests ----------


async def test_304_if_none_match_exact(tmp_path: Path) -> None:
    (tmp_path / "a.css").write_text("body{}")
    app = WhiteSnout(directory=str(tmp_path))
    client = ASGITestClient(app)
    r1 = await client.get("/a.css")
    etag = r1["headers"][b"etag"]
    r2 = await client.get("/a.css", headers=[(b"if-none-match", etag)])
    assert r2["status"] == 304
    assert r2["body"] == b""


async def test_304_if_none_match_wildcard(tmp_path: Path) -> None:
    (tmp_path / "a.css").write_text("body{}")
    app = WhiteSnout(directory=str(tmp_path))
    client = ASGITestClient(app)
    r = await client.get("/a.css", headers=[(b"if-none-match", b"*")])
    assert r["status"] == 304


async def test_200_if_none_match_no_match(tmp_path: Path) -> None:
    (tmp_path / "a.css").write_text("body{}")
    app = WhiteSnout(directory=str(tmp_path))
    client = ASGITestClient(app)
    r = await client.get("/a.css", headers=[(b"if-none-match", b'"wrong"')])
    assert r["status"] == 200


async def test_304_if_modified_since_after_mtime(tmp_path: Path) -> None:
    (tmp_path / "a.css").write_text("body{}")
    # Set mtime to known time in the past
    os.utime(tmp_path / "a.css", (1_600_000_000, 1_600_000_000))
    app = WhiteSnout(directory=str(tmp_path))
    client = ASGITestClient(app)
    # Tue, 26 Apr 2022 (after Sep 2020 mtime)
    r = await client.get(
        "/a.css",
        headers=[(b"if-modified-since", b"Tue, 26 Apr 2022 00:00:00 GMT")],
    )
    assert r["status"] == 304


async def test_200_if_modified_since_before_mtime(tmp_path: Path) -> None:
    (tmp_path / "a.css").write_text("body{}")
    os.utime(tmp_path / "a.css", (1_700_000_000, 1_700_000_000))
    app = WhiteSnout(directory=str(tmp_path))
    client = ASGITestClient(app)
    r = await client.get(
        "/a.css",
        headers=[(b"if-modified-since", b"Tue, 26 Apr 2022 00:00:00 GMT")],
    )
    assert r["status"] == 200


async def test_invalid_if_modified_since_treated_as_no_header(tmp_path: Path) -> None:
    (tmp_path / "a.css").write_text("body{}")
    app = WhiteSnout(directory=str(tmp_path))
    client = ASGITestClient(app)
    r = await client.get("/a.css", headers=[(b"if-modified-since", b"not a date")])
    assert r["status"] == 200


# ---------- Index files ----------


async def test_index_html_served_for_directory_request(tmp_path: Path) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "index.html").write_text("<h1>hi</h1>")
    app = WhiteSnout(directory=str(tmp_path))
    client = ASGITestClient(app)
    r = await client.get("/sub/")
    assert r["status"] == 200
    assert r["body"] == b"<h1>hi</h1>"


async def test_directory_without_trailing_slash_redirects(tmp_path: Path) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "index.html").write_text("hi")
    app = WhiteSnout(directory=str(tmp_path))
    client = ASGITestClient(app)
    r = await client.get("/sub")
    assert r["status"] == 301
    assert r["headers"][b"location"] == b"/sub/"


async def test_directory_without_index_returns_404(tmp_path: Path) -> None:
    sub = tmp_path / "empty"
    sub.mkdir()
    app = WhiteSnout(directory=str(tmp_path))
    client = ASGITestClient(app)
    r = await client.get("/empty/")
    assert r["status"] == 404


# ---------- ASGI scope edge cases ----------


async def test_non_http_scope_passes_to_inner_app(tmp_path: Path) -> None:
    received: list[dict] = []

    async def inner(scope, receive, send):
        received.append(scope)

    app = WhiteSnout(inner, directory=str(tmp_path))
    scope: dict = {"type": "lifespan"}

    async def receive() -> dict:
        return {"type": "lifespan.startup"}

    async def send(event: dict) -> None:
        pass

    await app(scope, receive, send)
    assert len(received) == 1


async def test_non_http_scope_no_inner_app_silently_drops(tmp_path: Path) -> None:
    app = WhiteSnout(directory=str(tmp_path))
    scope: dict = {"type": "websocket"}

    async def receive() -> dict:
        return {"type": "websocket.disconnect"}

    sent: list[dict] = []

    async def send(event: dict) -> None:
        sent.append(event)

    # No exception expected; nothing should be sent
    await app(scope, receive, send)
    assert sent == []


async def test_query_string_does_not_affect_resolution(tmp_path: Path) -> None:
    (tmp_path / "a.css").write_text("ok")
    app = WhiteSnout(directory=str(tmp_path))
    scope: dict = {
        "type": "http",
        "method": "GET",
        "path": "/a.css",
        "raw_path": b"/a.css",
        "query_string": b"v=123&x=y",
        "headers": [],
        "http_version": "1.1",
        "scheme": "http",
        "client": ("127.0.0.1", 1),
        "server": ("127.0.0.1", 8000),
    }
    body: list[bytes] = []
    start: dict = {}

    async def receive() -> dict:
        return {"type": "http.disconnect"}

    async def send(event: dict) -> None:
        nonlocal start
        if event["type"] == "http.response.start":
            start = event
        elif event["type"] == "http.response.body" and event.get("body"):
            body.append(event["body"])

    await app(scope, receive, send)
    assert start["status"] == 200
    assert b"".join(body) == b"ok"


# ---------- Large files / streaming path ----------


async def test_large_file_uses_streaming(tmp_path: Path) -> None:
    """Files larger than sync_threshold take the chunked streaming path."""
    payload = os.urandom(200 * 1024)  # 200 KB > 64 KB default
    (tmp_path / "big.bin").write_bytes(payload)
    app = WhiteSnout(directory=str(tmp_path))
    client = ASGITestClient(app)
    r = await client.get("/big.bin")
    assert r["status"] == 200
    assert r["body"] == payload


async def test_large_file_range(tmp_path: Path) -> None:
    payload = os.urandom(200 * 1024)
    (tmp_path / "big.bin").write_bytes(payload)
    app = WhiteSnout(directory=str(tmp_path))
    client = ASGITestClient(app)
    r = await client.get("/big.bin", headers=[(b"range", b"bytes=1000-1999")])
    assert r["status"] == 206
    assert r["body"] == payload[1000:2000]


async def test_zero_byte_file(tmp_path: Path) -> None:
    (tmp_path / "empty.txt").write_bytes(b"")
    app = WhiteSnout(directory=str(tmp_path))
    client = ASGITestClient(app)
    r = await client.get("/empty.txt")
    assert r["status"] == 200
    assert r["body"] == b""
    assert r["headers"][b"content-length"] == b"0"


# ---------- Concurrency ----------


async def test_concurrent_requests_same_file(tmp_path: Path) -> None:
    data = b"shared" * 100
    (tmp_path / "a.css").write_bytes(data)
    app = WhiteSnout(directory=str(tmp_path))
    client = ASGITestClient(app)
    results = await asyncio.gather(*(client.get("/a.css") for _ in range(20)))
    assert all(r["status"] == 200 for r in results)
    assert all(r["body"] == data for r in results)


async def test_concurrent_requests_different_files(tmp_path: Path) -> None:
    for i in range(10):
        (tmp_path / f"f{i}.txt").write_text(f"content {i}")
    app = WhiteSnout(directory=str(tmp_path))
    client = ASGITestClient(app)
    results = await asyncio.gather(*(client.get(f"/f{i}.txt") for i in range(10)))
    for i, r in enumerate(results):
        assert r["status"] == 200
        assert r["body"] == f"content {i}".encode()


# ---------- Cache invalidation ----------


async def test_invalidate_cache_picks_up_changes(tmp_path: Path) -> None:
    (tmp_path / "a.css").write_text("v1")
    app = WhiteSnout(directory=str(tmp_path))
    client = ASGITestClient(app)
    r1 = await client.get("/a.css")
    assert r1["body"] == b"v1"

    # Rewrite + invalidate
    (tmp_path / "a.css").write_text("v2-longer-content")
    app.invalidate_cache()
    r2 = await client.get("/a.css")
    assert r2["body"] == b"v2-longer-content"


# ---------- add_files / add_directory ----------


async def test_add_files_precedence_over_directory(tmp_path: Path) -> None:
    (tmp_path / "favicon.ico").write_bytes(b"FROM_DIR")
    other = tmp_path / "branding"
    other.mkdir()
    (other / "icon").write_bytes(b"FROM_FILES")

    app = WhiteSnout(directory=str(tmp_path))
    app.add_files({"/favicon.ico": str(other / "icon")})
    client = ASGITestClient(app)
    r = await client.get("/favicon.ico")
    assert r["body"] == b"FROM_FILES"


async def test_remove_files_falls_back_to_directory(tmp_path: Path) -> None:
    (tmp_path / "favicon.ico").write_bytes(b"FROM_DIR")
    other = tmp_path / "alt.ico"
    other.write_bytes(b"FROM_FILES")

    app = WhiteSnout(directory=str(tmp_path))
    app.add_files({"/favicon.ico": str(other)})
    client = ASGITestClient(app)
    r1 = await client.get("/favicon.ico")
    assert r1["body"] == b"FROM_FILES"

    app.remove_files("/favicon.ico")
    r2 = await client.get("/favicon.ico")
    assert r2["body"] == b"FROM_DIR"


async def test_remove_directory_invalidates_path_cache(
    tmp_path: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    main_dir = tmp_path_factory.mktemp("main")
    extra = tmp_path_factory.mktemp("extra")
    (extra / "f.txt").write_text("extra")

    app = WhiteSnout(directory=str(main_dir))
    app.add_directory("/extra", str(extra))
    client = ASGITestClient(app)
    r1 = await client.get("/extra/f.txt")
    assert r1["status"] == 200

    app.remove_directory("/extra")
    r2 = await client.get("/extra/f.txt")
    assert r2["status"] == 404


# ---------- Custom error responses ----------


async def test_custom_404_body(tmp_path: Path) -> None:
    app = WhiteSnout(
        directory=str(tmp_path), error_responses={404: b"Custom not found"}
    )
    client = ASGITestClient(app)
    r = await client.get("/missing.txt")
    assert r["status"] == 404
    assert r["body"] == b"Custom not found"


async def test_empty_error_bodies(tmp_path: Path) -> None:
    app = WhiteSnout(directory=str(tmp_path), error_responses={})
    client = ASGITestClient(app)
    r = await client.get("/missing.txt")
    assert r["status"] == 404
    assert r["body"] == b""


# ---------- Compressed pre-existing variants ----------


async def test_serves_br_when_offered(tmp_path: Path) -> None:
    (tmp_path / "a.css").write_text("body{}")
    (tmp_path / "a.css.br").write_bytes(b"brotli-fake")

    app = WhiteSnout(directory=str(tmp_path))
    client = ASGITestClient(app)
    r = await client.get("/a.css", headers=[(b"accept-encoding", b"br, gzip")])
    assert r["status"] == 200
    assert r["headers"].get(b"content-encoding") == b"br"
    assert r["body"] == b"brotli-fake"


async def test_serves_gz_when_only_gzip_offered(tmp_path: Path) -> None:
    (tmp_path / "a.css").write_text("body{}")
    (tmp_path / "a.css.gz").write_bytes(b"gz-fake")

    app = WhiteSnout(directory=str(tmp_path))
    client = ASGITestClient(app)
    r = await client.get("/a.css", headers=[(b"accept-encoding", b"gzip")])
    assert r["headers"].get(b"content-encoding") == b"gzip"


async def test_no_compression_when_client_does_not_accept(tmp_path: Path) -> None:
    (tmp_path / "a.css").write_text("body{}")
    (tmp_path / "a.css.gz").write_bytes(b"gz-fake")

    app = WhiteSnout(directory=str(tmp_path))
    client = ASGITestClient(app)
    r = await client.get("/a.css")
    assert b"content-encoding" not in r["headers"]
    assert r["body"] == b"body{}"


# ---------- Inner app delegation ----------


async def test_404_delegates_to_inner_app(tmp_path: Path) -> None:
    async def inner(scope, receive, send):
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"text/plain")],
            }
        )
        await send({"type": "http.response.body", "body": b"from-inner"})

    app = WhiteSnout(inner, directory=str(tmp_path))
    client = ASGITestClient(app)
    r = await client.get("/dynamic-route")
    assert r["status"] == 200
    assert r["body"] == b"from-inner"


# ---------- HEAD ----------


async def test_head_returns_headers_no_body(tmp_path: Path) -> None:
    payload = b"x" * 1000
    (tmp_path / "a.bin").write_bytes(payload)
    app = WhiteSnout(directory=str(tmp_path))

    scope: dict = {
        "type": "http",
        "method": "HEAD",
        "path": "/a.bin",
        "raw_path": b"/a.bin",
        "query_string": b"",
        "headers": [],
        "http_version": "1.1",
        "scheme": "http",
        "client": ("127.0.0.1", 1),
        "server": ("127.0.0.1", 8000),
    }
    body: list[bytes] = []
    start: dict = {}

    async def receive() -> dict:
        return {"type": "http.disconnect"}

    async def send(event: dict) -> None:
        nonlocal start
        if event["type"] == "http.response.start":
            start = event
        elif event["type"] == "http.response.body" and event.get("body"):
            body.append(event["body"])

    await app(scope, receive, send)
    assert start["status"] == 200
    assert b"".join(body) == b""
    headers = dict(start["headers"])
    assert headers[b"content-length"] == str(len(payload)).encode()


# ---------- OPTIONS ----------


async def test_options_cors_preflight_allowed(tmp_path: Path) -> None:
    app = WhiteSnout(directory=str(tmp_path), cors=True)

    scope: dict = {
        "type": "http",
        "method": "OPTIONS",
        "path": "/a.css",
        "raw_path": b"/a.css",
        "query_string": b"",
        "headers": [(b"origin", b"https://example.com")],
        "http_version": "1.1",
        "scheme": "http",
        "client": ("127.0.0.1", 1),
        "server": ("127.0.0.1", 8000),
    }
    start: dict = {}

    async def receive() -> dict:
        return {"type": "http.disconnect"}

    async def send(event: dict) -> None:
        nonlocal start
        if event["type"] == "http.response.start":
            start = event

    await app(scope, receive, send)
    assert start["status"] == 204


async def test_options_without_cors_returns_405(tmp_path: Path) -> None:
    app = WhiteSnout(directory=str(tmp_path))

    scope: dict = {
        "type": "http",
        "method": "OPTIONS",
        "path": "/a.css",
        "raw_path": b"/a.css",
        "query_string": b"",
        "headers": [],
        "http_version": "1.1",
        "scheme": "http",
        "client": ("127.0.0.1", 1),
        "server": ("127.0.0.1", 8000),
    }
    start: dict = {}

    async def receive() -> dict:
        return {"type": "http.disconnect"}

    async def send(event: dict) -> None:
        nonlocal start
        if event["type"] == "http.response.start":
            start = event

    await app(scope, receive, send)
    assert start["status"] == 405


# ---------- Logging configuration ----------


def test_log_level_none_silences_logger() -> None:
    import logging

    app = WhiteSnout(log_level=None)
    snout_logger = logging.getLogger("whitesnout")
    # When log_level=None, the logger is muted by setting level above CRITICAL
    assert snout_logger.level > logging.CRITICAL
    del app


def test_custom_log_level_applied() -> None:
    import logging

    app = WhiteSnout(log_level="WARNING")
    snout_logger = logging.getLogger("whitesnout")
    assert snout_logger.level == logging.WARNING
    del app
