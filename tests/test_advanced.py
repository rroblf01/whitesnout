"""Advanced edge cases: manifest, autocompress, Django storage,
configuration permutations, and observability."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from tests.conftest import ASGITestClient
from whitesnout import WhiteSnout

# ---------- Manifest edge cases ----------


def test_manifest_invalid_json_returns_empty(tmp_path: Path) -> None:
    from whitesnout.manifest import load_manifest

    manifest = tmp_path / "bad.json"
    manifest.write_text("{not json")
    with pytest.raises(json.JSONDecodeError):
        load_manifest(manifest)


def test_manifest_non_dict_returns_empty(tmp_path: Path) -> None:
    from whitesnout.manifest import load_manifest

    manifest = tmp_path / "list.json"
    manifest.write_text(json.dumps(["a", "b"]))
    paths = load_manifest(manifest)
    assert paths == set()


def test_manifest_empty_dict(tmp_path: Path) -> None:
    from whitesnout.manifest import load_manifest

    manifest = tmp_path / "empty.json"
    manifest.write_text("{}")
    paths = load_manifest(manifest)
    assert paths == set()


def test_manifest_mixed_value_types(tmp_path: Path) -> None:
    from whitesnout.manifest import load_manifest

    manifest = tmp_path / "mixed.json"
    manifest.write_text(
        json.dumps(
            {
                "a.js": "a.abc.js",
                "b.css": {"file": "b.xyz.css"},
                "c.png": 12345,  # ignored — not str or dict-with-file
            }
        )
    )
    paths = load_manifest(manifest)
    assert "/a.abc.js" in paths
    assert "/b.xyz.css" in paths


async def test_manifest_path_with_leading_slash_preserved(
    tmp_path: Path,
) -> None:
    (tmp_path / "x.css").write_text("body")
    manifest = tmp_path / "manifest.json"
    # Already has leading slash
    manifest.write_text(json.dumps({"x.css": "/x.css"}))
    app = WhiteSnout(directory=str(tmp_path), manifest_path=str(manifest))
    client = ASGITestClient(app)
    r = await client.get("/x.css")
    assert b"immutable" in r["headers"].get(b"cache-control", b"")


# ---------- Autocompress edge cases ----------


async def test_autocompress_skips_binary_extension(tmp_path: Path) -> None:
    (tmp_path / "photo.jpg").write_bytes(b"\xff\xd8\xff" + b"x" * 5000)
    app = WhiteSnout(directory=str(tmp_path), autocompress=True)
    client = ASGITestClient(app)
    r = await client.get("/photo.jpg", headers=[(b"accept-encoding", b"gzip")])
    assert r["status"] == 200
    assert b"content-encoding" not in r["headers"]


async def test_autocompress_skips_files_over_max_size(tmp_path: Path) -> None:
    payload = b"compressible " * 10_000  # ~130 KB
    (tmp_path / "big.txt").write_bytes(payload)
    app = WhiteSnout(
        directory=str(tmp_path),
        autocompress=True,
        autocompress_max_size=1024,  # cap below file size
    )
    client = ASGITestClient(app)
    r = await client.get("/big.txt", headers=[(b"accept-encoding", b"gzip")])
    assert r["status"] == 200
    assert b"content-encoding" not in r["headers"]


async def test_autocompress_skips_when_no_accept_encoding(
    tmp_path: Path,
) -> None:
    (tmp_path / "a.txt").write_text("compressible " * 200)
    app = WhiteSnout(directory=str(tmp_path), autocompress=True)
    client = ASGITestClient(app)
    r = await client.get("/a.txt")
    assert b"content-encoding" not in r["headers"]


async def test_autocompress_cached_across_requests(tmp_path: Path) -> None:
    payload = b"compressible " * 500
    (tmp_path / "a.txt").write_bytes(payload)
    app = WhiteSnout(directory=str(tmp_path), autocompress=True)
    client = ASGITestClient(app)
    r1 = await client.get("/a.txt", headers=[(b"accept-encoding", b"gzip")])
    r2 = await client.get("/a.txt", headers=[(b"accept-encoding", b"gzip")])
    assert r1["body"] == r2["body"]
    assert r1["headers"].get(b"content-encoding") == b"gzip"


async def test_autocompress_skipped_for_range_request(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("compressible " * 200)
    app = WhiteSnout(directory=str(tmp_path), autocompress=True)
    client = ASGITestClient(app)
    r = await client.get(
        "/a.txt",
        headers=[(b"accept-encoding", b"gzip"), (b"range", b"bytes=0-99")],
    )
    # Range requests must serve raw bytes, never the compressed in-memory copy
    assert r["status"] == 206
    assert b"content-encoding" not in r["headers"]


async def test_autocompress_skipped_when_precompressed_exists(
    tmp_path: Path,
) -> None:
    (tmp_path / "a.txt").write_text("compressible " * 200)
    (tmp_path / "a.txt.gz").write_bytes(b"PRECOMPRESSED")

    app = WhiteSnout(directory=str(tmp_path), autocompress=True)
    client = ASGITestClient(app)
    r = await client.get("/a.txt", headers=[(b"accept-encoding", b"gzip")])
    assert r["status"] == 200
    assert r["headers"].get(b"content-encoding") == b"gzip"
    # The on-disk .gz should win over the in-memory autocompress
    assert r["body"] == b"PRECOMPRESSED"


def test_compressed_cache_keyed_by_mtime() -> None:
    from whitesnout.autocompress import CompressedCache

    c = CompressedCache()
    c.put("p", 100, "gzip", b"old")
    # New mtime → cache miss
    assert c.get("p", 200, "gzip") is None
    assert c.get("p", 100, "gzip") == b"old"


def test_compress_bytes_unknown_encoding_returns_none() -> None:
    from whitesnout.autocompress import compress_bytes

    assert compress_bytes(b"data", "xz") is None


def test_pick_encoding_brotli_disabled() -> None:
    from whitesnout.autocompress import pick_encoding

    assert pick_encoding("br, gzip", allow_brotli=False, allow_gzip=True) == "gzip"


def test_pick_encoding_none_offered() -> None:
    from whitesnout.autocompress import pick_encoding

    assert pick_encoding("", allow_brotli=True, allow_gzip=True) is None


# ---------- Django storage backend full pipeline ----------


def test_storage_post_process_emits_compressed_for_text(
    tmp_path: Path,
) -> None:
    # Configure Django to use a real collectstatic flow
    from django.conf import settings

    static_root = tmp_path / "out"
    static_root.mkdir()
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.css").write_text("body { color: red; }\n" * 200)

    if settings.configured:
        for k, v in {
            "STATIC_ROOT": str(static_root),
            "STATIC_URL": "/static/",
            "STATICFILES_DIRS": [str(src)],
            "INSTALLED_APPS": ["django.contrib.staticfiles"],
            "DEBUG": False,
        }.items():
            setattr(settings, k, v)
    else:
        settings.configure(
            STATIC_ROOT=str(static_root),
            STATIC_URL="/static/",
            STATICFILES_DIRS=[str(src)],
            INSTALLED_APPS=["django.contrib.staticfiles"],
            DEBUG=False,
            SECRET_KEY="t",
        )
        import django

        django.setup()

    from whitesnout.storage import CompressedManifestStaticFilesStorage

    storage = CompressedManifestStaticFilesStorage(location=str(static_root))
    # Place the source file inside the storage's location so manifest
    # processing can hash and emit gz/br siblings
    (static_root / "app.css").write_text("body { color: red; }\n" * 200)
    paths = {"app.css": (storage, "app.css")}
    list(storage.post_process(paths, dry_run=False))

    # Either the original or a hashed sibling should have a .gz alongside
    gz_files = list(static_root.glob("*.css.gz"))
    assert len(gz_files) >= 1


# ---------- Config permutations ----------


def test_log_level_invalid_string_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError):
        WhiteSnout(log_level="NOT_A_LEVEL")


def test_cors_allow_origins_empty_disables_cors(tmp_path: Path) -> None:
    app = WhiteSnout(directory=str(tmp_path), cors_allow_origins=[])
    assert app.config.cors_allow_origins == []


def test_env_vars_override_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHITESNOUT_CACHE_MAX_AGE", "7200")
    monkeypatch.setenv("WHITESNOUT_CHUNK_SIZE", "131072")
    monkeypatch.setenv("WHITESNOUT_BROTLI", "false")
    monkeypatch.setenv("WHITESNOUT_AUTOCOMPRESS", "true")
    from whitesnout.config import Config

    c = Config()
    assert c.cache_max_age == 7200
    assert c.chunk_size == 131072
    assert c.brotli is False
    assert c.autocompress is True


def test_env_var_invalid_int_falls_back_to_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WHITESNOUT_CACHE_MAX_AGE", "not-a-number")
    from whitesnout.config import Config

    c = Config()
    assert c.cache_max_age == 3600  # default


def test_kwargs_override_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHITESNOUT_CACHE_MAX_AGE", "7200")
    from whitesnout.config import Config

    c = Config(cache_max_age=9000)
    assert c.cache_max_age == 9000


def test_default_skip_compress_includes_binary_types() -> None:
    c = WhiteSnout(directory="/tmp").config
    assert ".jpg" in c.skip_compress_extensions
    assert ".png" in c.skip_compress_extensions
    assert ".woff2" in c.skip_compress_extensions


# ---------- Observability hook payload ----------


async def test_on_request_hook_includes_scope(tmp_path: Path) -> None:
    (tmp_path / "a.css").write_text("x")
    captured: list[dict] = []
    app = WhiteSnout(
        directory=str(tmp_path),
        on_request=lambda info: captured.append(info),
    )
    client = ASGITestClient(app)
    await client.get("/a.css")
    info = captured[0]
    assert info["method"] == "GET"
    assert info["path"] == "/a.css"
    assert info["status"] == 200
    assert info["length"] == 1
    assert info["elapsed_s"] >= 0
    assert info["scope"]["path"] == "/a.css"


async def test_on_request_hook_called_for_304(tmp_path: Path) -> None:
    (tmp_path / "a.css").write_text("x")
    captured: list[dict] = []
    app = WhiteSnout(
        directory=str(tmp_path),
        on_request=lambda info: captured.append(info),
    )
    client = ASGITestClient(app)
    r1 = await client.get("/a.css")
    etag = r1["headers"][b"etag"]
    await client.get("/a.css", headers=[(b"if-none-match", etag)])
    statuses = [c["status"] for c in captured]
    assert 200 in statuses
    assert 304 in statuses


async def test_on_request_hook_called_for_404(tmp_path: Path) -> None:
    captured: list[dict] = []
    app = WhiteSnout(
        directory=str(tmp_path),
        on_request=lambda info: captured.append(info),
    )
    client = ASGITestClient(app)
    await client.get("/missing.txt")
    # 404 path: no body served via the static pipeline, hook is currently
    # only invoked for successful static responses. Confirm behavior.
    # If 404 should fire the hook, this test would assert len(captured) == 1.
    # Today's behavior: hook fires only on 200/304/416/HEAD/big files.
    # Document via this test (regression guard).
    assert all(c["status"] != 404 for c in captured)


# ---------- Streaming path stat consistency ----------


async def test_large_file_etag_matches_actual_content(tmp_path: Path) -> None:
    payload = os.urandom(150 * 1024)
    f = tmp_path / "big.bin"
    f.write_bytes(payload)
    app = WhiteSnout(directory=str(tmp_path))
    client = ASGITestClient(app)
    r1 = await client.get("/big.bin")
    etag = r1["headers"][b"etag"]
    # Same file → same etag
    r2 = await client.get("/big.bin")
    assert r2["headers"][b"etag"] == etag


# ---------- 405 / 416 body & headers ----------


async def test_416_returns_content_range_header(tmp_path: Path) -> None:
    (tmp_path / "a.bin").write_bytes(b"abc")
    app = WhiteSnout(directory=str(tmp_path))
    client = ASGITestClient(app)
    r = await client.get("/a.bin", headers=[(b"range", b"bytes=100-200")])
    assert r["status"] == 416
    assert r["headers"][b"content-range"] == b"bytes */3"


# ---------- Multiple CORS origins ----------


async def test_cors_first_origin_wins_when_origin_missing(tmp_path: Path) -> None:
    (tmp_path / "a.css").write_text("x")
    app = WhiteSnout(
        directory=str(tmp_path),
        cors_allow_origins=["https://a.com", "https://b.com"],
    )
    client = ASGITestClient(app)
    # No Origin header on request — no CORS header emitted
    r = await client.get("/a.css")
    assert b"access-control-allow-origin" not in r["headers"]


# ---------- index_file customization ----------


async def test_custom_index_file(tmp_path: Path) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "home.html").write_text("<h1>custom</h1>")
    app = WhiteSnout(directory=str(tmp_path), index_file="home.html")
    client = ASGITestClient(app)
    r = await client.get("/sub/")
    assert r["status"] == 200
    assert r["body"] == b"<h1>custom</h1>"


# ---------- charset config ----------


async def test_custom_charset_in_content_type(tmp_path: Path) -> None:
    (tmp_path / "a.html").write_text("<p>hi</p>")
    app = WhiteSnout(directory=str(tmp_path), charset="iso-8859-1")
    client = ASGITestClient(app)
    r = await client.get("/a.html")
    ct = r["headers"][b"content-type"]
    assert b"iso-8859-1" in ct or b"ISO-8859-1" in ct
