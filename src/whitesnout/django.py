"""Django integration for whitesnout.

Two patterns supported:

1. ASGI wrapper for `asgi.py`::

       # asgi.py
       from whitesnout.django import get_static_application
       application = get_static_application()

2. Manual wiring with the regular `WhiteSnout` class::

       from django.core.asgi import get_asgi_application
       from whitesnout import WhiteSnout

       asgi_app = get_asgi_application()
       application = WhiteSnout(asgi_app, directory=settings.STATIC_ROOT, ...)

`get_static_application()` reads Django settings (`STATIC_ROOT`, `STATIC_URL`,
`STATICFILES_STORAGE`) and wires `WhiteSnout` automatically, including
Django's `staticfiles.json` manifest when `ManifestStaticFilesStorage` is
in use.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from whitesnout.main import WhiteSnout


def get_static_application(
    asgi_app: Any | None = None,
    **overrides: Any,
) -> WhiteSnout:
    """Return a WhiteSnout instance wrapping Django's ASGI application.

    Reads Django settings (must be configured before this call):

    - ``STATIC_ROOT``           → ``directory``
    - ``STATIC_URL``            → used as prefix for `add_directory` if non-empty
    - ``STATICFILES_STORAGE``   → if it's a manifest storage, hooks the manifest

    Any keyword overrides are passed through to ``WhiteSnout``.
    """
    from django.conf import settings
    from django.core.asgi import get_asgi_application

    if asgi_app is None:
        asgi_app = get_asgi_application()

    static_root = getattr(settings, "STATIC_ROOT", None)
    if not static_root:
        raise RuntimeError(
            "settings.STATIC_ROOT is not configured; run `manage.py "
            "collectstatic` first or set STATIC_ROOT in settings."
        )

    static_url = getattr(settings, "STATIC_URL", "/static/") or "/static/"
    if not static_url.startswith("/"):
        static_url = "/" + static_url
    if not static_url.endswith("/"):
        static_url = static_url + "/"

    manifest_path: str | None = None
    storage = getattr(settings, "STATICFILES_STORAGE", "") or ""
    if "Manifest" in storage:
        candidate = Path(static_root) / "staticfiles.json"
        if candidate.is_file():
            manifest_path = str(candidate)

    kwargs: dict[str, Any] = {
        "directory": str(static_root),
        "manifest_path": manifest_path,
    }
    kwargs.update(overrides)

    snout = WhiteSnout(asgi_app, **kwargs)

    # Mount STATIC_URL prefix when it's not the root
    if static_url not in ("/", "/static/"):
        snout.add_directory(static_url.rstrip("/"), str(static_root))

    return snout


class WhiteSnoutMiddleware:
    """ASGI middleware factory for Django's MIDDLEWARE list.

    Use with ``django.urls`` ASGI deployments. Place near the top of the
    MIDDLEWARE list — static files should be served before authentication
    or session middleware runs.

    Example::

        MIDDLEWARE = [
            "whitesnout.django.WhiteSnoutMiddleware",
            ...
        ]
    """

    async_capable = True
    sync_capable = False

    def __init__(self, get_response: Any) -> None:
        from django.conf import settings

        self.get_response = get_response
        self._snout = WhiteSnout(
            directory=getattr(settings, "STATIC_ROOT", "static"),
            manifest_path=_django_manifest_path(),
        )

    async def __call__(self, request: Any) -> Any:
        # Static-file paths flow through WhiteSnout's ASGI interface; everything
        # else falls back to the regular Django response pipeline.
        from django.conf import settings

        static_url = (getattr(settings, "STATIC_URL", "/static/") or "/static/").rstrip(
            "/"
        ) + "/"
        if request.path.startswith(static_url):
            # Build a minimal ASGI scope-compatible call. Production-grade
            # users should prefer the ASGI wrapper get_static_application().
            from django.http import HttpResponse

            return HttpResponse(
                "WhiteSnoutMiddleware: use get_static_application() in asgi.py "
                "for production. Direct middleware mode is informational.",
                status=501,
            )
        return await self.get_response(request)


def _django_manifest_path() -> str | None:
    from django.conf import settings

    storage = getattr(settings, "STATICFILES_STORAGE", "") or ""
    if "Manifest" not in storage:
        return None
    static_root = getattr(settings, "STATIC_ROOT", None)
    if not static_root:
        return None
    candidate = Path(static_root) / "staticfiles.json"
    return str(candidate) if candidate.is_file() else None
