from __future__ import annotations

import os
import re
import stat as stat_module
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


def find_compressed(
    file_path: Path,
    accept_encoding: str,
) -> tuple[Path, str] | None:
    if "br" in accept_encoding.lower():
        br_path = file_path.with_suffix(file_path.suffix + ".br")
        if br_path.exists():
            return br_path, "br"

    if "gzip" in accept_encoding.lower():
        gz_path = file_path.with_suffix(file_path.suffix + ".gz")
        if gz_path.exists():
            return gz_path, "gzip"

    return None
