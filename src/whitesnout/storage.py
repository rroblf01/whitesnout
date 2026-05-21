"""Django staticfiles storage backends for whitesnout.

Drop in as ``STATICFILES_STORAGE`` (Django < 4.2) or in ``STORAGES``
(Django 4.2+) to make ``collectstatic`` hash filenames *and* emit
``.gz`` / ``.br`` siblings for serving with zero CPU at request time.

Example (Django 4.2+)::

    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "whitesnout.storage.CompressedManifestStaticFilesStorage",
        },
    }

The compressed storage skips already-compressed extensions (jpg, png,
webp, woff2, …) and avoids re-compressing files that haven't changed.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

_SKIP = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".woff",
    ".woff2",
    ".gz",
    ".br",
    ".zip",
    ".mp4",
    ".webm",
}


try:
    from django.contrib.staticfiles.storage import (
        ManifestStaticFilesStorage,
        StaticFilesStorage,
    )
except ImportError:  # pragma: no cover - Django is optional
    ManifestStaticFilesStorage = object  # type: ignore[assignment,misc]  # ty: ignore[invalid-assignment]
    StaticFilesStorage = object  # type: ignore[assignment,misc]  # ty: ignore[invalid-assignment]


def _compress_one(file_path: Path) -> tuple[int, int]:
    """Generate .gz + .br siblings for `file_path`. Returns (gz_made, br_made)."""
    if file_path.suffix.lower() in _SKIP:
        return (0, 0)
    if not file_path.is_file():
        return (0, 0)

    from whitesnout.compress import _compress_brotli, _compress_gzip

    gz = _compress_gzip(file_path, force=False)
    try:
        import brotli  # noqa: F401

        br = _compress_brotli(file_path, force=False)
    except ImportError:
        br = 0
    return (gz, br)


class CompressedStaticFilesStorage(StaticFilesStorage):  # type: ignore[misc,valid-type]
    """Plain (non-hashed) static files + gzip/brotli siblings."""

    def post_process(
        self, paths: dict, dry_run: bool = False, **options: Any
    ) -> Iterable[tuple[str, str, bool]]:
        if dry_run:
            return
        for name in paths:
            file_path = Path(self.path(name))
            gz, br = _compress_one(file_path)
            if gz or br:
                yield name, name, True


class CompressedManifestStaticFilesStorage(ManifestStaticFilesStorage):  # type: ignore[misc,valid-type]
    """Hashed static files (manifest) + gzip/brotli siblings."""

    def post_process(
        self, paths: dict, dry_run: bool = False, **options: Any
    ) -> Iterable[tuple[str, str, bool]]:
        # Let Django hash + write the files first
        super_results: list[tuple[str, str, bool | Exception]] = []
        for entry in super().post_process(paths, dry_run, **options):
            super_results.append(entry)
            yield entry

        if dry_run:
            return

        # Compress every hashed file that the parent emitted
        seen: set[str] = set()
        for _original_name, hashed_name, processed in super_results:
            if not processed or isinstance(processed, Exception):
                continue
            if hashed_name in seen:
                continue
            seen.add(hashed_name)
            file_path = Path(self.path(hashed_name))
            _compress_one(file_path)
