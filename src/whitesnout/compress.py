from __future__ import annotations

import fnmatch
import gzip
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

_DEFAULT_SKIP_EXTS = {
    ".gz",
    ".br",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".avif",
    ".woff",
    ".woff2",
    ".zip",
    ".mp4",
    ".webm",
    ".mp3",
    ".pdf",
}


def compress_directory(
    root: str,
    force: bool = False,
    *,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    jobs: int | None = None,
    quiet: bool = False,
) -> tuple[int, int, int]:
    """Compress files under ``root`` into ``.gz`` and ``.br`` siblings.

    Returns ``(gzip_count, brotli_count, skipped_count)``.

    - ``include`` / ``exclude``: glob patterns matched against the path
      relative to ``root`` (e.g. ``"**/*.css"`` or ``"vendor/**"``). Default
      excludes binary extensions that do not compress further.
    - ``jobs``: number of worker processes. Defaults to ``os.cpu_count()``.
    - ``quiet``: suppress summary output.
    """
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        if not quiet:
            print(f"Error: '{root}' is not a directory")
        return (0, 0, 0)

    try:
        import brotli  # noqa: F401

        has_brotli = True
    except ImportError:
        has_brotli = False
        if not quiet:
            print(
                "Warning: brotli not installed. "
                "Install with: uv add whitesnout[compress]"
            )

    targets = list(
        _select_files(root_path, include or [], exclude or [], _DEFAULT_SKIP_EXTS)
    )

    if not targets:
        if not quiet:
            print("No files matched.")
        return (0, 0, 0)

    work = [(str(p), force, has_brotli) for p in targets]
    workers = jobs or os.cpu_count() or 1

    count_gz = 0
    count_br = 0
    skipped = 0

    if workers <= 1 or len(work) < 2:
        for item in work:
            gz, br, sk = _compress_one(item)
            count_gz += gz
            count_br += br
            skipped += sk
    else:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(_compress_one, item) for item in work]
            for f in as_completed(futures):
                gz, br, sk = f.result()
                count_gz += gz
                count_br += br
                skipped += sk

    if not quiet:
        print(f"Compressed: {count_gz} gzip, {count_br} brotli", end="")
        if skipped:
            print(
                f" ({skipped} skipped, install brotli for brotli compression)",
                end="",
            )
        print()

    return (count_gz, count_br, skipped)


def _select_files(
    root: Path,
    include: list[str],
    exclude: list[str],
    skip_exts: set[str],
):
    for entry in root.rglob("*"):
        if not entry.is_file():
            continue
        suffix = entry.suffix.lower()
        if suffix in skip_exts:
            continue
        rel = str(entry.relative_to(root))
        if include and not any(fnmatch.fnmatch(rel, pat) for pat in include):
            continue
        if exclude and any(fnmatch.fnmatch(rel, pat) for pat in exclude):
            continue
        yield entry


def _compress_one(item: tuple[str, bool, bool]) -> tuple[int, int, int]:
    path_str, force, has_brotli = item
    path = Path(path_str)
    gz = _compress_gzip(path, force)
    br = _compress_brotli(path, force) if has_brotli else 0
    sk = 0 if has_brotli else 1
    return (gz, br, sk)


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
