from __future__ import annotations

import os
import re
import stat as stat_module
from contextlib import suppress
from pathlib import Path


def sanitize_path(root: str, requested_path: str) -> Path | None:
    root_resolved = Path(root).resolve()
    try:
        full = (root_resolved / requested_path.lstrip("/")).resolve()
    except (ValueError, RuntimeError):
        return None
    if not str(full).startswith(str(root_resolved) + os.sep) and str(full) != str(
        root_resolved
    ):
        return None
    if not full.exists():
        return None
    try:
        st = full.stat()
    except OSError:
        return None
    if not stat_module.S_ISREG(st.st_mode):
        return None
    return full


def resolve_directory(root: str, requested_path: str) -> Path | None:
    root_resolved = Path(root).resolve()
    try:
        full = (root_resolved / requested_path.lstrip("/")).resolve()
    except (ValueError, RuntimeError):
        return None
    if not str(full).startswith(str(root_resolved) + os.sep) and str(full) != str(
        root_resolved
    ):
        return None
    if not full.is_dir():
        return None
    return full


def resolve_index(dir_path: Path, index_file: str) -> Path | None:
    index = dir_path / index_file
    if index.is_file():
        return index
    return None


def file_stat(path: Path) -> os.stat_result | None:
    try:
        return path.stat()
    except OSError:
        return None


def is_hashed_file(filename: str, pattern: str) -> bool:
    return bool(re.search(pattern, filename))


def parse_accept_encoding(header: str) -> list[str]:
    """Parse Accept-Encoding header with quality values.

    Returns ordered list of encoding tokens (highest q first).
    """
    entries: list[tuple[float, str]] = []
    for part in header.split(","):
        part = part.strip()
        if not part:
            continue
        q = 1.0
        if ";" in part:
            token, params = part.split(";", 1)
            for param in params.split(";"):
                param = param.strip()
                if param.startswith("q="):
                    with suppress(ValueError):
                        q = float(param[2:])
        else:
            token = part
        entries.append((q, token.lower()))

    entries.sort(key=lambda x: x[0], reverse=True)
    return [token for _, token in entries]


def find_compressed(
    file_path: Path,
    accept_encoding: str,
    allow_brotli: bool = True,
    allow_gzip: bool = True,
) -> tuple[Path, str] | None:
    encodings = parse_accept_encoding(accept_encoding)

    for enc in encodings:
        if enc == "br" and allow_brotli:
            br_path = file_path.with_suffix(file_path.suffix + ".br")
            if br_path.exists():
                return br_path, "br"
        if enc == "gzip" and allow_gzip:
            gz_path = file_path.with_suffix(file_path.suffix + ".gz")
            if gz_path.exists():
                return gz_path, "gzip"

    return None
