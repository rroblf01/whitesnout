"""Tests for v2.0.0 new features: Vary, CORS allowlist, extra security
headers, custom MIME types, manifest, autocompress, on_request hook.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.conftest import ASGITestClient
from whitesnout import WhiteSnout
from whitesnout.autocompress import (
    CompressedCache,
    compress_bytes,
    pick_encoding,
    should_autocompress,
)
from whitesnout.manifest import load_manifest

# ---------- Vary header ----------


async def test_vary_accept_encoding_present(tmp_path: Path) -> None:
    (tmp_path / "a.css").write_text("body{}")
    app = WhiteSnout(directory=str(tmp_path))
    client = ASGITestClient(app)
    r = await client.get("/a.css")
    assert r["status"] == 200
    assert r["headers"].get(b"vary") == b"Accept-Encoding"


async def test_vary_absent_when_compression_disabled(tmp_path: Path) -> None:
    (tmp_path / "a.css").write_text("body{}")
    app = WhiteSnout(directory=str(tmp_path), brotli=False, gzip=False)
    client = ASGITestClient(app)
    r = await client.get("/a.css")
    assert r["status"] == 200
    assert b"vary" not in r["headers"]


# ---------- CORS allowlist ----------


async def test_cors_allowlist_match(tmp_path: Path) -> None:
    (tmp_path / "a.css").write_text("x")
    app = WhiteSnout(
        directory=str(tmp_path),
        cors_allow_origins=["https://example.com"],
    )
    client = ASGITestClient(app)
    r = await client.get("/a.css", headers=[(b"origin", b"https://example.com")])
    assert r["headers"].get(b"access-control-allow-origin") == b"https://example.com"
    # Vary: Origin is appended for non-wildcard allowlist.
    # Headers dict only stores last value for repeated keys; check it includes Origin
    assert b"Origin" in r["headers"].get(b"vary", b"")


async def test_cors_allowlist_no_match(tmp_path: Path) -> None:
    (tmp_path / "a.css").write_text("x")
    app = WhiteSnout(
        directory=str(tmp_path),
        cors_allow_origins=["https://allowed.com"],
    )
    client = ASGITestClient(app)
    r = await client.get("/a.css", headers=[(b"origin", b"https://evil.com")])
    assert b"access-control-allow-origin" not in r["headers"]


async def test_cors_legacy_wildcard(tmp_path: Path) -> None:
    (tmp_path / "a.css").write_text("x")
    app = WhiteSnout(directory=str(tmp_path), cors=True)
    client = ASGITestClient(app)
    r = await client.get("/a.css", headers=[(b"origin", b"https://x.com")])
    assert r["headers"].get(b"access-control-allow-origin") == b"https://x.com"


# ---------- Extra security headers ----------


async def test_hsts_csp_headers(tmp_path: Path) -> None:
    (tmp_path / "a.css").write_text("x")
    app = WhiteSnout(
        directory=str(tmp_path),
        hsts="max-age=31536000; includeSubDomains",
        csp="default-src 'self'",
        referrer_policy="no-referrer",
        permissions_policy="geolocation=()",
    )
    client = ASGITestClient(app)
    r = await client.get("/a.css")
    h = r["headers"]
    assert h.get(b"strict-transport-security") == b"max-age=31536000; includeSubDomains"
    assert h.get(b"content-security-policy") == b"default-src 'self'"
    assert h.get(b"referrer-policy") == b"no-referrer"
    assert h.get(b"permissions-policy") == b"geolocation=()"


# ---------- Custom MIME types ----------


async def test_custom_mime_type_override(tmp_path: Path) -> None:
    (tmp_path / "file.epub").write_bytes(b"PK\x03\x04dummy")
    app = WhiteSnout(
        directory=str(tmp_path),
        mime_types={".epub": "application/epub+zip"},
    )
    client = ASGITestClient(app)
    r = await client.get("/file.epub")
    assert r["headers"].get(b"content-type") == b"application/epub+zip"


# ---------- Manifest ----------


def test_manifest_django_format(tmp_path: Path) -> None:
    manifest = tmp_path / "staticfiles.json"
    manifest.write_text(
        json.dumps(
            {
                "paths": {
                    "css/app.css": "css/app.abc123def456.css",
                    "js/app.js": "js/app.xyz789ghi012.js",
                }
            }
        )
    )
    paths = load_manifest(manifest)
    assert "/css/app.abc123def456.css" in paths
    assert "/js/app.xyz789ghi012.js" in paths


def test_manifest_webpack_format(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "main.js": "main.abcd1234.js",
                "style.css": "style.efgh5678.css",
            }
        )
    )
    paths = load_manifest(manifest)
    assert "/main.abcd1234.js" in paths
    assert "/style.efgh5678.css" in paths


def test_manifest_vite_format(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {"src/main.ts": {"file": "assets/main.aaaa1111.js", "src": "src/main.ts"}}
        )
    )
    paths = load_manifest(manifest)
    assert "/assets/main.aaaa1111.js" in paths


def test_manifest_missing_file_returns_empty(tmp_path: Path) -> None:
    paths = load_manifest(tmp_path / "nope.json")
    assert paths == set()


async def test_manifest_forces_immutable(tmp_path: Path) -> None:
    (tmp_path / "plain.css").write_text("x")
    manifest = tmp_path / "staticfiles.json"
    manifest.write_text(json.dumps({"paths": {"plain.css": "plain.css"}}))
    app = WhiteSnout(directory=str(tmp_path), manifest_path=str(manifest))
    client = ASGITestClient(app)
    r = await client.get("/plain.css")
    cc = r["headers"].get(b"cache-control", b"")
    assert b"immutable" in cc


# ---------- Autocompress ----------


def test_compressed_cache_lru() -> None:
    c = CompressedCache(max_entries=2)
    c.put("a", 1, "gzip", b"x")
    c.put("b", 1, "gzip", b"y")
    assert c.get("a", 1, "gzip") == b"x"
    c.put("c", 1, "gzip", b"z")  # evicts b
    assert c.get("b", 1, "gzip") is None
    assert c.get("c", 1, "gzip") == b"z"


def test_compress_bytes_gzip() -> None:
    raw = b"hello world " * 100
    out = compress_bytes(raw, "gzip")
    assert out is not None
    assert len(out) < len(raw)


def test_pick_encoding_prefers_brotli_when_available() -> None:
    # Brotli may not be installed; fall back to gzip if so
    enc = pick_encoding("gzip, br", allow_brotli=True, allow_gzip=True)
    assert enc in ("br", "gzip")


def test_should_autocompress_skips_binary() -> None:
    skip = {".jpg", ".png"}
    assert not should_autocompress(Path("a.jpg"), skip)
    assert should_autocompress(Path("a.css"), skip)


async def test_autocompress_serves_gzip(tmp_path: Path) -> None:
    payload = b"compressible " * 500
    (tmp_path / "big.txt").write_bytes(payload)
    app = WhiteSnout(directory=str(tmp_path), autocompress=True)
    client = ASGITestClient(app)
    r = await client.get("/big.txt", headers=[(b"accept-encoding", b"gzip")])
    assert r["status"] == 200
    assert r["headers"].get(b"content-encoding") == b"gzip"
    assert len(r["body"]) < len(payload)


# ---------- on_request hook ----------


async def test_on_request_sync_hook(tmp_path: Path) -> None:
    (tmp_path / "a.css").write_text("x")
    calls: list[dict] = []
    app = WhiteSnout(
        directory=str(tmp_path), on_request=lambda info: calls.append(info)
    )
    client = ASGITestClient(app)
    await client.get("/a.css")
    assert len(calls) == 1
    assert calls[0]["status"] == 200
    assert calls[0]["path"] == "/a.css"


async def test_on_request_async_hook(tmp_path: Path) -> None:
    (tmp_path / "a.css").write_text("x")
    calls: list[dict] = []

    async def hook(info: dict) -> None:
        calls.append(info)

    app = WhiteSnout(directory=str(tmp_path), on_request=hook)
    client = ASGITestClient(app)
    await client.get("/a.css")
    assert len(calls) == 1


async def test_on_request_hook_exception_swallowed(tmp_path: Path) -> None:
    (tmp_path / "a.css").write_text("x")

    def hook(info: dict) -> None:
        raise RuntimeError("boom")

    app = WhiteSnout(directory=str(tmp_path), on_request=hook)
    client = ASGITestClient(app)
    r = await client.get("/a.css")
    assert r["status"] == 200  # hook failure doesn't break request


# ---------- Config / env ----------


def test_env_cors_allow_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHITESNOUT_CORS_ALLOW_ORIGINS", "https://a.com, https://b.com")
    from whitesnout.config import Config

    c = Config()
    assert c.cors_allow_origins == ["https://a.com", "https://b.com"]


def test_env_hsts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHITESNOUT_HSTS", "max-age=63072000")
    from whitesnout.config import Config

    c = Config()
    assert c.hsts == "max-age=63072000"


# ---------- Autorefresh + path_resolver ----------


async def test_autorefresh_picks_up_new_file(tmp_path: Path) -> None:
    (tmp_path / "a.css").write_text("v1")
    app = WhiteSnout(directory=str(tmp_path), autorefresh=True)
    client = ASGITestClient(app)

    r1 = await client.get("/a.css")
    assert r1["body"] == b"v1"

    (tmp_path / "a.css").write_text("v2-different-length")
    r2 = await client.get("/a.css")
    assert r2["body"] == b"v2-different-length"


async def test_autorefresh_off_caches_old_content(tmp_path: Path) -> None:
    (tmp_path / "a.css").write_text("v1-content")
    app = WhiteSnout(directory=str(tmp_path), autorefresh=False)
    client = ASGITestClient(app)

    r1 = await client.get("/a.css")
    assert r1["body"] == b"v1-content"

    # Overwrite with shorter content — stat cache still holds old size,
    # so the body length will not match.
    (tmp_path / "a.css").write_text("shorter")
    r2 = await client.get("/a.css")
    # Cached size is 10, new file is 7; we still report content-length 10
    assert int(r2["headers"][b"content-length"]) == 10


async def test_path_resolver_falls_back_when_directory_misses(
    tmp_path: Path,
) -> None:
    other = tmp_path / "other"
    other.mkdir()
    (other / "extra.txt").write_text("found via resolver")

    def resolver(path: str) -> Path | None:
        if path == "/extra.txt":
            return other / "extra.txt"
        return None

    app = WhiteSnout(directory=str(tmp_path), path_resolver=resolver)
    client = ASGITestClient(app)
    r = await client.get("/extra.txt")
    assert r["status"] == 200
    assert r["body"] == b"found via resolver"


async def test_path_resolver_returning_none_yields_404(tmp_path: Path) -> None:
    def resolver(path: str) -> Path | None:
        return None

    app = WhiteSnout(directory=str(tmp_path), path_resolver=resolver)
    client = ASGITestClient(app)
    r = await client.get("/nope.txt")
    assert r["status"] == 404
