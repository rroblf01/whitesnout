"""Security-focused tests: path traversal, symlink escape, header injection."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from tests.conftest import ASGITestClient
from whitesnout import WhiteSnout
from whitesnout.file_handler import resolve_directory, sanitize_path

# ---------- Path traversal ----------


@pytest.mark.parametrize(
    "evil_path",
    [
        "/../secret.txt",
        "/../../etc/passwd",
        "/foo/../../etc/passwd",
        "/foo/../../../bar",
        "/./../foo",
        "/foo/./../../bar",
        "//etc/passwd",
        "/foo//../bar",
        "/foo/./bar/../../baz",
    ],
)
def test_sanitize_path_blocks_traversal(tmp_path: Path, evil_path: str) -> None:
    (tmp_path / "ok.txt").write_text("safe")
    result = sanitize_path(str(tmp_path), evil_path)
    if result is not None:
        assert str(result).startswith(str(tmp_path.resolve()))


@pytest.mark.parametrize(
    "evil_path",
    [
        "../etc/passwd",
        "../../etc/passwd",
        "..%2f..%2fetc%2fpasswd",
        "%2e%2e%2fetc",
    ],
)
def test_sanitize_path_no_leading_slash(tmp_path: Path, evil_path: str) -> None:
    result = sanitize_path(str(tmp_path), evil_path)
    if result is not None:
        assert str(result).startswith(str(tmp_path.resolve()))


def test_sanitize_path_null_byte(tmp_path: Path) -> None:
    # Null bytes either reject (None) or stay within root — never escape
    result = sanitize_path(str(tmp_path), "/file\x00.txt")
    if result is not None:
        assert str(result).startswith(str(tmp_path.resolve()))


def test_resolve_directory_blocks_traversal(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    result = resolve_directory(str(tmp_path), "/sub/../..")
    # Either None or stays within root
    if result is not None:
        assert str(result).startswith(str(tmp_path.resolve()))


async def test_request_traversal_returns_404(tmp_path: Path) -> None:
    (tmp_path / "public.txt").write_text("public")
    parent = tmp_path.parent
    secret = parent / "secret.txt"
    secret.write_text("PRIVATE")
    try:
        app = WhiteSnout(directory=str(tmp_path))
        client = ASGITestClient(app)
        r = await client.get("/../secret.txt")
        assert r["status"] == 404
        assert b"PRIVATE" not in r["body"]
    finally:
        secret.unlink(missing_ok=True)


# ---------- Symbolic link policy ----------


@pytest.mark.skipif(
    sys.platform == "win32", reason="symlinks need privilege on Windows"
)
async def test_symlink_inside_root_is_served(tmp_path: Path) -> None:
    target = tmp_path / "target.txt"
    target.write_text("real content")
    link = tmp_path / "link.txt"
    link.symlink_to(target)

    app = WhiteSnout(directory=str(tmp_path))
    client = ASGITestClient(app)
    r = await client.get("/link.txt")
    assert r["status"] == 200
    assert r["body"] == b"real content"


@pytest.mark.skipif(
    sys.platform == "win32", reason="symlinks need privilege on Windows"
)
async def test_symlink_escaping_root_is_blocked(tmp_path: Path) -> None:
    inside = tmp_path / "inside"
    inside.mkdir()
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("OUTSIDE")
    bad_link = inside / "escape.txt"
    bad_link.symlink_to(outside_file)

    app = WhiteSnout(directory=str(inside))
    client = ASGITestClient(app)
    r = await client.get("/escape.txt")
    assert r["status"] == 404
    assert b"OUTSIDE" not in r["body"]


# ---------- Non-regular files ----------


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX FIFOs only")
def test_sanitize_rejects_fifo(tmp_path: Path) -> None:
    fifo = tmp_path / "pipe"
    os.mkfifo(fifo)
    result = sanitize_path(str(tmp_path), "/pipe")
    assert result is None


def test_sanitize_rejects_directory(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    result = sanitize_path(str(tmp_path), "/sub")
    assert result is None


# ---------- Header injection ----------


async def test_filename_with_newline_does_not_inject_headers(tmp_path: Path) -> None:
    # Reserved by OS — won't actually create a file with embedded \n on most FS,
    # but the request path should never break header structure.
    app = WhiteSnout(directory=str(tmp_path))
    client = ASGITestClient(app)
    r = await client.get("/foo\r\nInjected: yes\r\nbar")
    assert r["status"] == 404
    assert b"Injected" not in r["body"]


async def test_directory_traversal_with_query_string(tmp_path: Path) -> None:
    parent = tmp_path.parent
    secret = parent / "secret_qs.txt"
    secret.write_text("PRIVATE")
    try:
        app = WhiteSnout(directory=str(tmp_path))
        client = ASGITestClient(app)
        r = await client.get("/../secret_qs.txt")
        assert r["status"] == 404
    finally:
        secret.unlink(missing_ok=True)


# ---------- Forbidden methods ----------


async def test_post_without_inner_app_returns_405(tmp_path: Path) -> None:
    (tmp_path / "a.css").write_text("x")
    app = WhiteSnout(directory=str(tmp_path))
    scope: dict = {
        "type": "http",
        "method": "POST",
        "path": "/a.css",
        "raw_path": b"/a.css",
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
    assert start["status"] == 405


async def test_put_delete_etc_405(tmp_path: Path) -> None:
    (tmp_path / "a.css").write_text("x")
    app = WhiteSnout(directory=str(tmp_path))

    for method in ("PUT", "DELETE", "PATCH", "TRACE"):
        scope: dict = {
            "type": "http",
            "method": method,
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
        assert start["status"] == 405, f"{method} should return 405"
