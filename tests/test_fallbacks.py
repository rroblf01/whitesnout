"""Tests for the pure-Python fallback paths.

These force ``_RUST_AVAILABLE = False`` on each module so the Python
implementations are exercised. Keeps the no-Rust install (or arch without
a pre-built wheel) from regressing silently.
"""

from __future__ import annotations

import email.utils
from pathlib import Path

import pytest

# ---------- response.py fallbacks ----------


def test_compute_etag_python_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    from whitesnout import response as resp

    monkeypatch.setattr(resp, "_RUST_AVAILABLE", False)
    etag = resp.compute_etag(size=1234, mtime_ns=999_000_000_000)
    assert etag.startswith('"')
    assert etag.endswith('"')
    # mtime_ns:x-size:x
    assert "4d2" in etag  # 1234 in hex


def test_format_last_modified_python_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from whitesnout import response as resp

    monkeypatch.setattr(resp, "_RUST_AVAILABLE", False)
    s = resp.format_last_modified(1_700_000_000_000_000_000)
    assert "GMT" in s


def test_parse_range_python_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    from whitesnout import response as resp

    monkeypatch.setattr(resp, "_RUST_AVAILABLE", False)
    assert resp.parse_range("bytes=0-99", 1000) == (0, 99)
    assert resp.parse_range("bytes=-50", 1000) == (950, 999)
    assert resp.parse_range("bytes=900-", 1000) == (900, 999)
    assert resp.parse_range("invalid", 1000) is None
    assert resp.parse_range("bytes=1000-2000", 1000) is None
    assert resp.parse_range("bytes=", 1000) is None


def test_build_content_range_python_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from whitesnout import response as resp

    monkeypatch.setattr(resp, "_RUST_AVAILABLE", False)
    assert resp.build_content_range(10, 20, 100) == b"bytes 10-20/100"


def test_build_headers_python_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    from whitesnout import response as resp

    monkeypatch.setattr(resp, "_RUST_AVAILABLE", False)
    headers = resp.build_headers(
        content_type="text/plain",
        content_length=42,
        extra=[(b"x-foo", b"bar")],
    )
    assert (b"content-type", b"text/plain") in headers
    assert (b"content-length", b"42") in headers
    assert (b"x-foo", b"bar") in headers


def test_security_headers_python_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from whitesnout import response as resp

    monkeypatch.setattr(resp, "_RUST_AVAILABLE", False)
    on = resp.security_headers(True)
    assert (b"x-content-type-options", b"nosniff") in on
    assert (b"x-frame-options", b"DENY") in on
    assert resp.security_headers(False) == []


def test_check_304_python_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    from whitesnout import response as resp

    monkeypatch.setattr(resp, "_RUST_AVAILABLE", False)
    etag = '"abc"'
    headers = [(b"if-none-match", b'"abc"')]
    assert resp.check_304(headers, etag, "") is True
    assert resp.check_304([(b"if-none-match", b"*")], etag, "") is True
    assert resp.check_304([(b"if-none-match", b'"xyz"')], etag, "") is False


def test_check_304_python_fallback_if_modified_since(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from whitesnout import response as resp

    monkeypatch.setattr(resp, "_RUST_AVAILABLE", False)
    lm = email.utils.formatdate(1_600_000_000, usegmt=True)
    later = email.utils.formatdate(1_700_000_000, usegmt=True)
    assert resp.check_304([(b"if-modified-since", later.encode())], "", lm) is True


# ---------- file_handler.py fallbacks ----------


def test_parse_accept_encoding_python_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from whitesnout import file_handler as fh

    monkeypatch.setattr(fh, "_RUST_AVAILABLE", False)
    result = fh.parse_accept_encoding("gzip;q=0.5, br;q=1.0, identity;q=0")
    # Sorted by q descending: br > gzip > identity
    assert result[0] == "br"
    assert "gzip" in result
    assert "identity" in result


def test_parse_accept_encoding_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    from whitesnout import file_handler as fh

    monkeypatch.setattr(fh, "_RUST_AVAILABLE", False)
    assert fh.parse_accept_encoding("") == []


def test_parse_accept_encoding_malformed_q(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from whitesnout import file_handler as fh

    monkeypatch.setattr(fh, "_RUST_AVAILABLE", False)
    # Bad q value should be tolerated (defaults to 1.0)
    result = fh.parse_accept_encoding("br;q=oops, gzip")
    assert "br" in result
    assert "gzip" in result


def test_is_hashed_file_python_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    from whitesnout import file_handler as fh

    monkeypatch.setattr(fh, "_RUST_AVAILABLE", False)
    assert fh.is_hashed_file("app.abc12345.css", r"\.[a-f0-9]{8,}\.")
    assert not fh.is_hashed_file("app.css", r"\.[a-f0-9]{8,}\.")
    # Empty pattern matches everywhere; ensure no crash
    assert fh.is_hashed_file("anything", "") is True


def test_find_compressed_python_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from whitesnout import file_handler as fh

    monkeypatch.setattr(fh, "_RUST_AVAILABLE", False)
    target = tmp_path / "a.css"
    target.write_text("body")
    (tmp_path / "a.css.gz").write_bytes(b"gz")
    result = fh.find_compressed(target, "gzip", allow_brotli=False, allow_gzip=True)
    assert result is not None
    assert result[1] == "gzip"


def test_find_compressed_returns_none_when_no_variant(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from whitesnout import file_handler as fh

    monkeypatch.setattr(fh, "_RUST_AVAILABLE", False)
    target = tmp_path / "a.css"
    target.write_text("body")
    assert fh.find_compressed(target, "gzip") is None


# ---------- utils.py fallbacks ----------


def test_guess_content_type_python_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from whitesnout import utils as u

    monkeypatch.setattr(u, "_RUST_AVAILABLE", False)
    # Text types get charset
    assert "text/html" in u.guess_content_type("a.html")
    assert "charset" in u.guess_content_type("a.html")
    # JSON gets charset
    assert "application/json" in u.guess_content_type("a.json")
    # Binary types do not
    assert "image/png" in u.guess_content_type("a.png")
    assert "charset" not in u.guess_content_type("a.png")
    # Unknown extension
    assert u.guess_content_type("a.unknownext").startswith("application/octet-stream")


def test_guess_content_type_no_extension(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from whitesnout import utils as u

    monkeypatch.setattr(u, "_RUST_AVAILABLE", False)
    assert u.guess_content_type("nodot").startswith("application/octet-stream")


def test_guess_content_type_uppercase_ext(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from whitesnout import utils as u

    monkeypatch.setattr(u, "_RUST_AVAILABLE", False)
    assert "text/html" in u.guess_content_type("INDEX.HTML")


# ---------- cache.py fallbacks ----------


def test_lru_python_fallback_basic() -> None:
    from whitesnout.cache import _PyLRUCache

    c: _PyLRUCache = _PyLRUCache(maxsize=3)
    c.put("a", 1)
    c.put("b", 2)
    c.put("c", 3)
    assert c.get("a") == 1
    c.put("d", 4)  # evicts b (least recently used)
    assert c.get("b") is None
    assert c.get("a") == 1
    assert c.get("d") == 4


def test_lru_python_fallback_clear() -> None:
    from whitesnout.cache import _PyLRUCache

    c: _PyLRUCache = _PyLRUCache(maxsize=2)
    c.put("a", 1)
    c.put("b", 2)
    c.clear()
    assert c.get("a") is None
    assert c.get("b") is None


def test_stat_cache_python_fallback() -> None:
    from whitesnout.cache import _PyStatCache

    c = _PyStatCache(maxsize=2)
    c.put("k", 100, 200)
    assert c.get("k") == (100, 200)
    c.put("k2", 300, 400)
    c.put("k3", 500, 600)  # evicts k
    assert c.get("k") is None


# ---------- build_response_pipeline Python branch ----------


async def test_pipeline_works_with_python_stat_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Force the non-fused fallback path by passing a Python StatCache."""
    from whitesnout import response as resp

    (tmp_path / "a.css").write_text("hello")

    # Use a pure-Python stat cache so the Rust fused call is bypassed
    from whitesnout.cache import _PyStatCache

    py_cache = _PyStatCache(maxsize=64)
    file_path = tmp_path / "a.css"
    serve_path, headers, status, length, range_spec, is_304, _ce = (
        resp.build_response_pipeline(
            file_path,
            py_cache,
            "",
            allow_brotli=True,
            allow_gzip=True,
            filename="a.css",
            charset="utf-8",
            cache_max_age=3600,
            immutable_max_age=31536000,
            immutable_pattern=r"\.[a-f0-9]{8,}\.",
            security_enabled=True,
            cors_enabled=False,
            range_header=None,
            method="GET",
            if_none_match=None,
            if_modified_since=None,
        )
    )
    assert status == 200
    assert length == 5
    assert is_304 is False


# ---------- compress.py ImportError fallback ----------


def test_compress_directory_without_brotli(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    tmp_path: Path,
) -> None:
    (tmp_path / "a.css").write_text("body{}")

    # Force the brotli import to fail inside compress_directory
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "brotli":
            raise ImportError("simulated")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    from whitesnout.compress import compress_directory

    compress_directory(str(tmp_path))
    out = capsys.readouterr().out
    assert "brotli not installed" in out
    # gzip still happens
    assert (tmp_path / "a.css.gz").is_file()
