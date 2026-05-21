"""Django integration for whitesnout.

Whitesnout is ASGI-native and so this integration only supports Django ASGI
deployments. For Django WSGI / classic `runserver` mode, stick with
`whitenoise`. Whitenoise's middleware works in WSGI because WSGI is a strict
sync request/response cycle; ASGI's streaming nature makes the equivalent
middleware pattern brittle, so we expose only the `asgi.py` wrapper.

Typical use::

    # asgi.py
    import os
    import django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
    django.setup()

    from whitesnout.django import get_static_application
    application = get_static_application()

In development, pass ``use_finders=True`` to skip ``collectstatic``::

    application = get_static_application(use_finders=True, autorefresh=True)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from whitesnout.main import WhiteSnout


def get_static_application(
    asgi_app: Any | None = None,
    *,
    use_finders: bool = False,
    autorefresh: bool | None = None,
    **overrides: Any,
) -> WhiteSnout:
    """Return a WhiteSnout instance wrapping Django's ASGI application.

    Reads Django settings (must be configured before this call):

    - ``STATIC_ROOT``         → ``directory``
    - ``STATIC_URL``          → mount prefix when non-trivial
    - ``STATICFILES_STORAGE`` → if a manifest storage is configured, hooks
      ``static/staticfiles.json`` automatically
    - ``DEBUG``               → if True and ``autorefresh`` is unset, enables
      ``autorefresh=True``

    Parameters
    ----------
    asgi_app
        The inner ASGI application. Defaults to Django's
        ``get_asgi_application()``.
    use_finders
        Resolve missing files via ``django.contrib.staticfiles.finders.find``
        so ``collectstatic`` is not required during development.
    autorefresh
        Clear the path and stat caches on every request. Default: follow
        ``settings.DEBUG``.
    **overrides
        Forwarded to :class:`whitesnout.main.WhiteSnout`.
    """
    from django.conf import settings
    from django.core.asgi import get_asgi_application

    if asgi_app is None:
        asgi_app = get_asgi_application()

    static_root = getattr(settings, "STATIC_ROOT", None)
    static_url = (getattr(settings, "STATIC_URL", "/static/") or "/static/")
    if not static_url.startswith("/"):
        static_url = "/" + static_url
    if not static_url.endswith("/"):
        static_url = static_url + "/"

    if not static_root and not use_finders:
        raise RuntimeError(
            "settings.STATIC_ROOT is not configured; run `manage.py "
            "collectstatic` first, set STATIC_ROOT in settings, or pass "
            "use_finders=True for development mode."
        )

    if autorefresh is None:
        autorefresh = bool(getattr(settings, "DEBUG", False))

    manifest_path: str | None = _django_manifest_path()

    kwargs: dict[str, Any] = {
        "directory": str(static_root) if static_root else ".",
        "manifest_path": manifest_path,
        "autorefresh": autorefresh,
    }

    if use_finders:
        kwargs["path_resolver"] = _build_finders_resolver(static_url)

    kwargs.update(overrides)

    snout = WhiteSnout(asgi_app, **kwargs)

    # Mount STATIC_URL prefix when it isn't `/static/` (the implicit default
    # WhiteSnout uses when serving from `directory`).
    if static_root and static_url not in ("/", "/static/"):
        snout.add_directory(static_url.rstrip("/"), str(static_root))

    return snout


def _build_finders_resolver(static_url: str):
    """Return a callable that resolves a request path to a file via Django's
    staticfiles finders. Used in development to avoid running collectstatic.
    """
    prefix = static_url
    prefix_len = len(prefix)

    def resolve(path: str) -> Path | None:
        if not path.startswith(prefix):
            return None
        relative = path[prefix_len:]
        if not relative:
            return None
        from django.contrib.staticfiles.finders import find

        found = find(relative)
        if found:
            return Path(found)
        return None

    return resolve


def _django_manifest_path() -> str | None:
    from django.conf import settings

    storage = getattr(settings, "STATICFILES_STORAGE", "") or ""
    storages = getattr(settings, "STORAGES", None)
    if storages and isinstance(storages, dict):
        staticfiles = storages.get("staticfiles", {})
        if isinstance(staticfiles, dict):
            backend = staticfiles.get("BACKEND", "") or ""
            if "Manifest" in backend:
                storage = backend

    if "Manifest" not in storage:
        return None
    static_root = getattr(settings, "STATIC_ROOT", None)
    if not static_root:
        return None
    candidate = Path(static_root) / "staticfiles.json"
    return str(candidate) if candidate.is_file() else None
