"""Tests for the X-Request-ID header propagation feature."""

from __future__ import annotations

import re
from pathlib import Path

from tests.conftest import ASGITestClient
from whitesnout import WhiteSnout

_UUID_HEX = re.compile(r"^[0-9a-f]{32}$")


async def test_request_id_disabled_by_default(tmp_path: Path) -> None:
    (tmp_path / "a.css").write_text("x")
    app = WhiteSnout(directory=str(tmp_path))
    client = ASGITestClient(app)
    r = await client.get("/a.css")
    assert b"x-request-id" not in r["headers"]


async def test_request_id_generated_when_missing(tmp_path: Path) -> None:
    (tmp_path / "a.css").write_text("x")
    app = WhiteSnout(directory=str(tmp_path), request_id_header="X-Request-ID")
    client = ASGITestClient(app)
    r = await client.get("/a.css")
    rid = r["headers"][b"x-request-id"]
    assert _UUID_HEX.match(rid.decode())


async def test_request_id_echoed_when_provided(tmp_path: Path) -> None:
    (tmp_path / "a.css").write_text("x")
    app = WhiteSnout(directory=str(tmp_path), request_id_header="X-Request-ID")
    client = ASGITestClient(app)
    r = await client.get(
        "/a.css", headers=[(b"x-request-id", b"client-supplied-12345")]
    )
    assert r["headers"][b"x-request-id"] == b"client-supplied-12345"


async def test_request_id_present_on_404(tmp_path: Path) -> None:
    app = WhiteSnout(directory=str(tmp_path), request_id_header="X-Request-ID")
    client = ASGITestClient(app)
    r = await client.get("/missing.css")
    assert r["status"] == 404
    assert b"x-request-id" in r["headers"]


async def test_request_id_present_on_health(tmp_path: Path) -> None:
    app = WhiteSnout(
        directory=str(tmp_path),
        health_check_path="/healthz",
        request_id_header="X-Request-ID",
    )
    client = ASGITestClient(app)
    r = await client.get("/healthz")
    assert r["status"] == 200
    assert b"x-request-id" in r["headers"]


async def test_request_id_present_on_304(tmp_path: Path) -> None:
    (tmp_path / "a.css").write_text("x")
    app = WhiteSnout(directory=str(tmp_path), request_id_header="X-Request-ID")
    client = ASGITestClient(app)
    # First request to learn the etag
    r1 = await client.get("/a.css")
    etag = r1["headers"][b"etag"]
    # Conditional request → 304
    r2 = await client.get("/a.css", headers=[(b"if-none-match", etag)])
    assert r2["status"] == 304
    assert b"x-request-id" in r2["headers"]


async def test_request_id_in_on_request_hook(tmp_path: Path) -> None:
    (tmp_path / "a.css").write_text("x")
    seen: list[dict] = []

    def hook(info: dict) -> None:
        seen.append(info)

    app = WhiteSnout(
        directory=str(tmp_path),
        request_id_header="X-Request-ID",
        on_request=hook,
    )
    client = ASGITestClient(app)
    await client.get("/a.css", headers=[(b"x-request-id", b"corr-abc")])
    assert seen[0]["request_id"] == "corr-abc"


async def test_request_id_custom_header_name(tmp_path: Path) -> None:
    (tmp_path / "a.css").write_text("x")
    app = WhiteSnout(directory=str(tmp_path), request_id_header="X-Trace-Id")
    client = ASGITestClient(app)
    r = await client.get("/a.css", headers=[(b"x-trace-id", b"trace-99")])
    assert r["headers"][b"x-trace-id"] == b"trace-99"


async def test_request_id_present_on_405(tmp_path: Path) -> None:
    app = WhiteSnout(directory=str(tmp_path), request_id_header="X-Request-ID")
    scope: dict = {
        "type": "http",
        "method": "DELETE",
        "path": "/x",
        "raw_path": b"/x",
        "query_string": b"",
        "headers": [(b"x-request-id", b"rid-42")],
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
    headers = dict(start["headers"])
    assert headers.get(b"x-request-id") == b"rid-42"
