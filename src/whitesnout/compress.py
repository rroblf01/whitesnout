from __future__ import annotations

import gzip
from pathlib import Path


def compress_directory(root: str, force: bool = False) -> None:
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        print(f"Error: '{root}' is not a directory")
        return

    try:
        import brotli  # noqa: F401

        has_brotli = True
    except ImportError:
        has_brotli = False
        print(
            "Warning: brotli not installed. Install with: uv add whitesnout[compress]"
        )

    count_gz = 0
    count_br = 0
    skipped = 0

    for entry in root_path.rglob("*"):
        if not entry.is_file():
            continue
        if entry.suffix in (".gz", ".br"):
            continue

        count_gz += _compress_gzip(entry, force)
        if has_brotli:
            count_br += _compress_brotli(entry, force)
        else:
            skipped += 1

    print(f"Compressed: {count_gz} gzip, {count_br} brotli", end="")
    if skipped:
        print(f" ({skipped} skipped, install brotli for brotli compression)", end="")
    print()


def _compress_gzip(path: Path, force: bool) -> int:
    import io

    gz_path = path.with_suffix(path.suffix + ".gz")
    if not _needs_update(path, gz_path, force):
        return 0
    data = path.read_bytes()
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as f:
        f.write(data)
    gz_path.write_bytes(buf.getvalue())
    return 1


def _compress_brotli(path: Path, force: bool) -> int:
    import brotli

    br_path = path.with_suffix(path.suffix + ".br")
    if not _needs_update(path, br_path, force):
        return 0
    data = path.read_bytes()
    compressed = brotli.compress(data, quality=6)
    br_path.write_bytes(compressed)
    return 1


def _needs_update(source: Path, target: Path, force: bool) -> bool:
    if force:
        return True
    if not target.exists():
        return True
    return source.stat().st_mtime > target.stat().st_mtime
