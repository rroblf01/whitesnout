"""ASGI entry point with whitesnout serving static files."""
from __future__ import annotations

import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
django.setup()

from whitesnout.django import get_static_application  # noqa: E402

# In DEBUG mode, autorefresh + use_finders kick in automatically so you do
# not need to run `collectstatic` while iterating on assets.
application = get_static_application(
    use_finders=os.environ.get("DJANGO_DEBUG", "0") == "1",
    hsts="max-age=31536000; includeSubDomains",
    csp="default-src 'self'",
    cors_allow_origins=["https://app.example.com"],
)
