from __future__ import annotations

import gzip
import os
from pathlib import Path

import brotli
import pytest

from whitesnout.compress import _needs_update, compress_directory


@pytest.fixture
def tmp_static(tmp_path: Path) -> Path:
    (tmp_path / "css").mkdir()
    (tmp_path / "js").mkdir()
    (tmp_path / "index.html").write_text("<html></html>")
    (tmp_path / "css/style.css").write_text("body {}")
    (tmp_path / "js/app.js").write_text("console.log(1);")
    return tmp_path


def test_compress_directory_creates_gz_and_br(tmp_static: Path) -> None:
    compress_directory(str(tmp_static))
    assert (tmp_static / "index.html.gz").exists()
    assert (tmp_static / "index.html.br").exists()
    assert (tmp_static / "css/style.css.gz").exists()
    assert (tmp_static / "css/style.css.br").exists()
    assert (tmp_static / "js/app.js.gz").exists()
    assert (tmp_static / "js/app.js.br").exists()


def test_compressed_content_is_valid_gzip(tmp_static: Path) -> None:
    compress_directory(str(tmp_static))
    data = (tmp_static / "index.html.gz").read_bytes()
    decompressed = gzip.decompress(data)
    assert decompressed == b"<html></html>"


def test_compressed_content_is_valid_brotli(tmp_static: Path) -> None:
    compress_directory(str(tmp_static))
    data = (tmp_static / "index.html.br").read_bytes()
    decompressed = brotli.decompress(data)
    assert decompressed == b"<html></html>"


def test_compress_skips_existing_up_to_date(tmp_static: Path) -> None:
    compress_directory(str(tmp_static))
    mtime_before = (tmp_static / "index.html.gz").stat().st_mtime
    compress_directory(str(tmp_static))
    mtime_after = (tmp_static / "index.html.gz").stat().st_mtime
    assert mtime_after == mtime_before


def test_compress_rebuilds_when_source_newer(tmp_static: Path) -> None:
    compress_directory(str(tmp_static))
    mtime_before = (tmp_static / "index.html.gz").stat().st_mtime
    os.utime(tmp_static / "index.html", (mtime_before + 10, mtime_before + 10))
    compress_directory(str(tmp_static))
    mtime_after = (tmp_static / "index.html.gz").stat().st_mtime
    assert mtime_after > mtime_before


def test_compress_force_rebuilds(tmp_static: Path) -> None:
    compress_directory(str(tmp_static))
    mtime_before = (tmp_static / "index.html.gz").stat().st_mtime
    compress_directory(str(tmp_static), force=True)
    mtime_after = (tmp_static / "index.html.gz").stat().st_mtime
    assert mtime_after >= mtime_before


def test_needs_update_no_target(tmp_static: Path) -> None:
    source = tmp_static / "index.html"
    target = tmp_static / "index.html.gz"
    assert _needs_update(source, target, force=False)


def test_needs_update_target_newer(tmp_static: Path) -> None:
    source = tmp_static / "index.html"
    target = tmp_static / "index.html.gz"
    target.write_text("dummy")
    os.utime(target, (source.stat().st_mtime + 100, source.stat().st_mtime + 100))
    assert not _needs_update(source, target, force=False)


def test_needs_update_force(tmp_static: Path) -> None:
    source = tmp_static / "index.html"
    target = tmp_static / "index.html.gz"
    target.write_text("dummy")
    assert _needs_update(source, target, force=True)
