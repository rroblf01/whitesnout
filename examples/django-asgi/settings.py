"""Minimal Django settings for the whitesnout ASGI example.

Real projects should split this into ``base.py`` / ``prod.py`` / ``dev.py``.
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "insecure-dev-only-change-me")
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.staticfiles",
]

MIDDLEWARE: list[str] = []

ROOT_URLCONF = "urls"

ASGI_APPLICATION = "asgi.application"

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "assets"]

# Whitesnout's compressed manifest storage replaces the default. After
# ``manage.py collectstatic``, every file in STATIC_ROOT is hashed and emitted
# with ``.gz`` + ``.br`` siblings.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitesnout.storage.CompressedManifestStaticFilesStorage",
    },
}

USE_TZ = True
