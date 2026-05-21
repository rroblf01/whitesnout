"""Tests for whitesnout.django + whitesnout.storage.

Django is configured per-test via `settings.configure(...)` so the suite
does not need a full project layout.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# ----------------------------------------------------------------------
# Django settings bootstrap helpers
# ----------------------------------------------------------------------


def _configure_django(**overrides) -> None:
    """Configure Django settings inline. Safe to call multiple times — the
    second call updates settings in place rather than re-configuring.
    """
    from django.conf import settings

    defaults: dict = {
        "DEBUG": False,
        "SECRET_KEY": "test",
        "STATIC_URL": "/static/",
        "INSTALLED_APPS": ["django.contrib.staticfiles"],
        "STATICFILES_FINDERS": [
            "django.contrib.staticfiles.finders.FileSystemFinder",
            "django.contrib.staticfiles.finders.AppDirectoriesFinder",
        ],
        "STATICFILES_DIRS": [],
        "ROOT_URLCONF": __name__,
    }
    defaults.update(overrides)

    if settings.configured:
        for k, v in defaults.items():
            setattr(settings, k, v)
    else:
        settings.configure(**defaults)
        import django

        django.setup()


# Minimal urlconf so get_asgi_application() works
urlpatterns: list = []


# ----------------------------------------------------------------------
# whitesnout.django
# ----------------------------------------------------------------------


def test_get_static_application_requires_static_root_unless_use_finders(
    tmp_path: Path,
) -> None:
    _configure_django(STATIC_ROOT=None)
    from whitesnout.django import get_static_application

    with pytest.raises(RuntimeError, match="STATIC_ROOT is not configured"):
        get_static_application()


def test_get_static_application_use_finders_skips_static_root_requirement(
    tmp_path: Path,
) -> None:
    _configure_django(STATIC_ROOT=None)
    from whitesnout.django import get_static_application

    snout = get_static_application(use_finders=True)
    assert snout.config.path_resolver is not None
    # Finders resolver is generated only when use_finders=True


def test_get_static_application_detects_manifest_django_storage(
    tmp_path: Path,
) -> None:
    static_root = tmp_path / "static"
    static_root.mkdir()
    (static_root / "staticfiles.json").write_text(
        json.dumps({"paths": {"app.css": "app.abc12345.css"}})
    )

    _configure_django(
        STATIC_ROOT=str(static_root),
        STATICFILES_STORAGE=(
            "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
        ),
    )
    from whitesnout.django import get_static_application

    snout = get_static_application()
    assert snout.config.manifest_path == str(static_root / "staticfiles.json")
    assert "/app.abc12345.css" in snout._manifest_paths


def test_get_static_application_detects_manifest_via_storages_dict(
    tmp_path: Path,
) -> None:
    static_root = tmp_path / "static"
    static_root.mkdir()
    (static_root / "staticfiles.json").write_text(json.dumps({"paths": {}}))

    _configure_django(
        STATIC_ROOT=str(static_root),
        STORAGES={
            "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
            "staticfiles": {
                "BACKEND": (
                    "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
                )
            },
        },
    )
    from whitesnout.django import get_static_application

    snout = get_static_application()
    assert snout.config.manifest_path == str(static_root / "staticfiles.json")


def test_autorefresh_defaults_to_debug(tmp_path: Path) -> None:
    static_root = tmp_path / "static"
    static_root.mkdir()

    _configure_django(STATIC_ROOT=str(static_root), DEBUG=True)
    from whitesnout.django import get_static_application

    snout = get_static_application()
    assert snout.config.autorefresh is True

    _configure_django(STATIC_ROOT=str(static_root), DEBUG=False)
    snout = get_static_application()
    assert snout.config.autorefresh is False


def test_get_static_application_mounts_non_default_static_url(
    tmp_path: Path,
) -> None:
    static_root = tmp_path / "static"
    static_root.mkdir()

    _configure_django(
        STATIC_ROOT=str(static_root),
        STATIC_URL="/assets/",
    )
    from whitesnout.django import get_static_application

    snout = get_static_application()
    prefixes = [p for p, _ in snout._extra_dirs]
    assert "/assets" in prefixes


# ----------------------------------------------------------------------
# Finders resolver behavior
# ----------------------------------------------------------------------


async def test_finders_resolver_resolves_static_path(tmp_path: Path) -> None:
    finder_root = tmp_path / "app_static"
    finder_root.mkdir()
    (finder_root / "logo.png").write_bytes(b"\x89PNG")

    _configure_django(
        STATIC_ROOT=str(tmp_path / "static"),
        STATICFILES_DIRS=[str(finder_root)],
        DEBUG=True,
    )
    from tests.conftest import ASGITestClient
    from whitesnout.django import get_static_application

    snout = get_static_application(use_finders=True)
    client = ASGITestClient(snout)
    r = await client.get("/static/logo.png")
    assert r["status"] == 200
    assert r["body"].startswith(b"\x89PNG")


# ----------------------------------------------------------------------
# whitesnout.storage
# ----------------------------------------------------------------------


def test_compressed_manifest_storage_generates_gz_br(tmp_path: Path) -> None:
    _configure_django(
        STATIC_ROOT=str(tmp_path / "static_out"),
        STATICFILES_DIRS=[],
    )
    (tmp_path / "static_out").mkdir()

    from whitesnout.storage import CompressedManifestStaticFilesStorage

    # Instantiate to verify the class is importable / constructible
    CompressedManifestStaticFilesStorage(location=str(tmp_path / "static_out"))

    # Drop a fake hashed file in the storage location
    asset_name = "app.abc12345.css"
    target = tmp_path / "static_out" / asset_name
    target.write_text("body { color: red; }\n" * 50)
    # Pretend post_process emitted this — call _compress_one helper directly
    from whitesnout.storage import _compress_one

    gz, _br = _compress_one(target)
    assert gz == 1
    assert target.with_suffix(target.suffix + ".gz").is_file()


def test_compressed_storage_skips_binary(tmp_path: Path) -> None:
    from whitesnout.storage import _compress_one

    img = tmp_path / "photo.jpg"
    img.write_bytes(b"\xff\xd8\xff" + b"x" * 1000)
    gz, br = _compress_one(img)
    assert (gz, br) == (0, 0)
    assert not img.with_suffix(img.suffix + ".gz").exists()
