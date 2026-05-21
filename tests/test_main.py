from __future__ import annotations

import pytest

from whitesnout import WhiteSnout

from .conftest import ASGITestClient, read_test_file


@pytest.fixture
def client() -> ASGITestClient:
    app = WhiteSnout(directory="tests/static")
    return ASGITestClient(app)


@pytest.mark.asyncio
async def test_serves_existing_file(client: ASGITestClient) -> None:
    resp = await client.get("/hello.txt")
    assert resp["status"] == 200
    assert resp["body"] == read_test_file("static/hello.txt")
    assert resp["headers"][b"content-type"] == b"text/plain; charset=utf-8"
    assert int(resp["headers"][b"content-length"]) > 0


@pytest.mark.asyncio
async def test_returns_not_found(client: ASGITestClient) -> None:
    resp = await client.get("/nonexistent.txt")
    assert resp["status"] == 404


@pytest.mark.asyncio
async def test_returns_not_found_for_path_traversal(client: ASGITestClient) -> None:
    resp = await client.get("/../../../etc/passwd")
    assert resp["status"] == 404


@pytest.mark.asyncio
async def test_head_request_no_body(client: ASGITestClient) -> None:
    await client.get("/hello.txt", headers=[(b"HEAD", b"")])
    # Reset - do HEAD via scope method if needed
    scope = {
        "type": "http",
        "method": "HEAD",
        "path": "/hello.txt",
        "raw_path": b"/hello.txt",
        "query_string": b"",
        "headers": [],
        "http_version": "1.1",
        "scheme": "http",
        "client": ("127.0.0.1", 50000),
        "server": ("127.0.0.1", 8000),
    }
    body_chunks: list[bytes] = []
    response_start = {}

    async def receive():
        return {"type": "http.disconnect"}

    async def send(event):
        nonlocal response_start
        if event["type"] == "http.response.start":
            response_start = event
        elif event["type"] == "http.response.body" and event.get("body"):
            body_chunks.append(event["body"])

    app = WhiteSnout(directory="tests/static")
    await app(scope, receive, send)
    assert response_start["status"] == 200
    assert b"content-length" in dict(response_start.get("headers", []))
    assert b"".join(body_chunks) == b""


@pytest.mark.asyncio
async def test_method_not_allowed() -> None:
    app = WhiteSnout(directory="tests/static")
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/hello.txt",
        "raw_path": b"/hello.txt",
        "query_string": b"",
        "headers": [],
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
    assert response_start["status"] == 405


@pytest.mark.asyncio
async def test_content_type_css(client: ASGITestClient) -> None:
    resp = await client.get("/css/style.css")
    assert resp["status"] == 200
    assert resp["headers"][b"content-type"] == b"text/css; charset=utf-8"


@pytest.mark.asyncio
async def test_content_type_html(client: ASGITestClient) -> None:
    resp = await client.get("/subdir/test.html")
    assert resp["status"] == 200
    assert resp["headers"][b"content-type"] == b"text/html; charset=utf-8"


@pytest.mark.asyncio
async def test_etag_header_present(client: ASGITestClient) -> None:
    resp = await client.get("/hello.txt")
    assert resp["status"] == 200
    etag = resp["headers"].get(b"etag")
    assert etag is not None
    assert etag.startswith(b'"')
    assert etag.endswith(b'"')


@pytest.mark.asyncio
async def test_last_modified_header_present(client: ASGITestClient) -> None:
    resp = await client.get("/hello.txt")
    assert resp["status"] == 200
    assert resp["headers"].get(b"last-modified") is not None


@pytest.mark.asyncio
async def test_cache_control_header_present(client: ASGITestClient) -> None:
    resp = await client.get("/hello.txt")
    assert resp["status"] == 200
    cc = resp["headers"].get(b"cache-control")
    assert cc is not None
    assert b"public" in cc
    assert b"max-age=3600" in cc


@pytest.mark.asyncio
async def test_immutable_cache_for_hashed_file(client: ASGITestClient) -> None:
    resp = await client.get("/css/styles.a1b2c3d4.css")
    assert resp["status"] == 200
    cc = resp["headers"].get(b"cache-control")
    assert cc is not None
    assert b"public" in cc
    assert b"immutable" in cc
    assert b"max-age=31536000" in cc


@pytest.mark.asyncio
async def test_304_not_modified_with_valid_etag(client: ASGITestClient) -> None:
    resp = await client.get("/hello.txt")
    etag = resp["headers"][b"etag"]

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/hello.txt",
        "raw_path": b"/hello.txt",
        "query_string": b"",
        "headers": [(b"if-none-match", etag)],
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

    app = WhiteSnout(directory="tests/static")
    await app(scope, receive, send)
    assert response_start["status"] == 304
    assert b"".join(body_chunks) == b""


@pytest.mark.asyncio
async def test_304_not_modified_with_if_modified_since(client: ASGITestClient) -> None:
    import calendar
    import email.utils

    resp = await client.get("/hello.txt")
    last_modified = resp["headers"][b"last-modified"]

    parsed = email.utils.parsedate(last_modified.decode())
    future = calendar.timegm(parsed) + 3600
    future_str = email.utils.formatdate(future, usegmt=True)

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/hello.txt",
        "raw_path": b"/hello.txt",
        "query_string": b"",
        "headers": [(b"if-modified-since", future_str.encode())],
        "http_version": "1.1",
        "scheme": "http",
        "client": ("127.0.0.1", 50000),
        "server": ("127.0.0.1", 8000),
    }
    response_start = {}

    async def receive():
        return {"type": "http.disconnect"}

    async def send(event):
        nonlocal response_start
        if event["type"] == "http.response.start":
            response_start = event

    app = WhiteSnout(directory="tests/static")
    await app(scope, receive, send)
    assert response_start["status"] == 304


@pytest.mark.asyncio
async def test_serves_index_for_root(client: ASGITestClient) -> None:
    resp = await client.get("/")
    assert resp["status"] == 200
    assert resp["body"] == read_test_file("static/index.html")


@pytest.mark.asyncio
async def test_redirects_directory_to_trailing_slash(client: ASGITestClient) -> None:
    resp = await client.get("/subdir")
    assert resp["status"] == 301
    assert resp["headers"][b"location"] == b"/subdir/"


@pytest.mark.asyncio
async def test_404_for_directory_without_index(client: ASGITestClient) -> None:
    resp = await client.get("/css/")
    assert resp["status"] == 404


@pytest.mark.asyncio
async def test_404_for_subdir_without_index(client: ASGITestClient) -> None:
    resp = await client.get("/subdir/")
    assert resp["status"] == 404


@pytest.mark.asyncio
async def test_passes_to_inner_app_when_not_found() -> None:
    inner_response = {"called": False}

    async def inner_app(scope, receive, send):
        inner_response["called"] = True
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"text/plain")],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": b"from inner",
                "more_body": False,
            }
        )

    app = WhiteSnout(inner_app, directory="tests/static")
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/nonexistent.txt",
        "raw_path": b"/nonexistent.txt",
        "query_string": b"",
        "headers": [],
        "http_version": "1.1",
        "scheme": "http",
        "client": ("127.0.0.1", 50000),
        "server": ("127.0.0.1", 8000),
    }
    body_chunks = []

    async def receive():
        return {"type": "http.disconnect"}

    async def send(event):
        if event["type"] == "http.response.body":
            body_chunks.append(event.get("body", b""))

    await app(scope, receive, send)
    assert inner_response["called"]
    assert b"from inner" in b"".join(body_chunks)


@pytest.mark.asyncio
async def test_security_headers_present(client: ASGITestClient) -> None:
    app = WhiteSnout(directory="tests/static", security_headers=True)
    resp = await client_get(app, "/hello.txt")
    assert resp["status"] == 200
    assert resp["headers"][b"x-content-type-options"] == b"nosniff"
    assert resp["headers"][b"x-frame-options"] == b"DENY"


@pytest.mark.asyncio
async def test_security_headers_disabled_by_default(client: ASGITestClient) -> None:
    app = WhiteSnout(directory="tests/static", security_headers=False)
    resp = await client_get(app, "/hello.txt")
    assert b"x-content-type-options" not in resp["headers"]
    assert b"x-frame-options" not in resp["headers"]


@pytest.mark.asyncio
async def test_security_headers_default_enabled() -> None:
    app = WhiteSnout(directory="tests/static")
    resp = await client_get(app, "/hello.txt")
    assert resp["headers"][b"x-content-type-options"] == b"nosniff"
    assert resp["headers"][b"x-frame-options"] == b"DENY"


@pytest.mark.asyncio
async def test_range_request_partial(client: ASGITestClient) -> None:
    app = WhiteSnout(directory="tests/static")
    resp = await client_get(
        app,
        "/hello.txt",
        extra_headers=[(b"range", b"bytes=0-4")],
    )
    assert resp["status"] == 206
    assert resp["headers"][b"content-range"] == b"bytes 0-4/14"
    assert resp["body"] == b"Hello"


@pytest.mark.asyncio
async def test_range_request_suffix(client: ASGITestClient) -> None:
    app = WhiteSnout(directory="tests/static")
    resp = await client_get(
        app,
        "/hello.txt",
        extra_headers=[(b"range", b"bytes=-4")],
    )
    assert resp["status"] == 206
    assert resp["body"] == b"ld!\n"


@pytest.mark.asyncio
async def test_range_not_satisfiable(client: ASGITestClient) -> None:
    app = WhiteSnout(directory="tests/static")
    resp = await client_get(
        app,
        "/hello.txt",
        extra_headers=[(b"range", b"bytes=100-110")],
    )
    assert resp["status"] == 416
    assert resp["headers"][b"content-range"] == b"bytes */14"
    assert b"content-type" in resp["headers"]


@pytest.mark.asyncio
async def test_range_ignored_with_nonexistent_file(client: ASGITestClient) -> None:
    app = WhiteSnout(directory="tests/static")
    resp = await client_get(
        app,
        "/nope.txt",
        extra_headers=[(b"range", b"bytes=0-4")],
    )
    assert resp["status"] == 404


@pytest.mark.asyncio
async def test_accept_encoding_quality_values() -> None:
    app = WhiteSnout(directory="tests/static")
    resp = await client_get(app, "/hello.txt", accept_encoding="br;q=0.1, gzip")
    assert resp["status"] == 200
    assert resp["headers"][b"content-encoding"] == b"gzip"


@pytest.mark.asyncio
async def test_cors_headers_present() -> None:
    app = WhiteSnout(directory="tests/static", cors=True)
    resp = await client_get(app, "/hello.txt")
    assert resp["status"] == 200
    assert resp["headers"][b"access-control-allow-origin"] == b"*"


@pytest.mark.asyncio
async def test_cors_disabled_by_default(client: ASGITestClient) -> None:
    resp = await client.get("/hello.txt")
    assert b"access-control-allow-origin" not in resp["headers"]


@pytest.mark.asyncio
async def test_cors_preflight() -> None:
    app = WhiteSnout(directory="tests/static", cors=True)
    scope: dict = {
        "type": "http",
        "method": "OPTIONS",
        "path": "/hello.txt",
        "raw_path": b"/hello.txt",
        "query_string": b"",
        "headers": [],
        "http_version": "1.1",
        "scheme": "http",
        "client": ("127.0.0.1", 50000),
        "server": ("127.0.0.1", 8000),
    }
    response_start: dict = {}
    body_chunks: list[bytes] = []

    async def receive():
        return {"type": "http.disconnect"}

    async def send(event):
        nonlocal response_start
        if event["type"] == "http.response.start":
            response_start = event
        elif event["type"] == "http.response.body":
            body_chunks.append(event.get("body", b""))

    await app(scope, receive, send)
    assert response_start["status"] == 204
    headers = dict(response_start.get("headers", []))
    assert headers[b"access-control-allow-origin"] == b"*"


@pytest.mark.asyncio
async def test_invalidate_cache() -> None:
    from whitesnout import WhiteSnout

    app = WhiteSnout(directory="tests/static")
    # Stat a real file to get a valid stat_result
    from pathlib import Path

    st = Path("tests/static/hello.txt").stat()
    app._stat_cache.put("test_key", st)
    assert app._stat_cache.get("test_key") is not None
    app.invalidate_cache()
    assert app._stat_cache.get("test_key") is None


@pytest.mark.asyncio
async def test_logging(caplog: pytest.LogCaptureFixture) -> None:
    import logging

    from whitesnout import WhiteSnout

    logger = logging.getLogger("whitesnout")
    logger.setLevel(logging.INFO)

    app = WhiteSnout(directory="tests/static")
    resp = await client_get(app, "/hello.txt")
    assert resp["status"] == 200
    assert len(caplog.records) >= 1
    assert caplog.records[-1].name == "whitesnout"


async def client_get(
    app, path: str, accept_encoding: str = "", extra_headers: list | None = None
) -> dict:
    headers = list(extra_headers or [])
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
    return {
        "status": response_start.get("status", 500),
        "headers": dict(response_start.get("headers", [])),
        "body": b"".join(body_chunks),
    }
