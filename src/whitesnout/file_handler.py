from __future__ import annotations

import os
import stat as stat_module
from pathlib import Path


def sanitize_path(root: str, requested_path: str) -> Path | None:
    root_resolved = Path(root).resolve()
    try:
        full = (root_resolved / requested_path.lstrip("/")).resolve()
    except (ValueError, RuntimeError):
        return None
    if not str(full).startswith(str(root_resolved) + os.sep) and str(full) != str(root_resolved):
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


def file_stat(path: Path) -> os.stat_result | None:
    try:
        return path.stat()
    except OSError:
        return None


def is_hashed_file(filename: str, pattern: str) -> bool:
    import re
    return bool(re.search(pattern, filename))
