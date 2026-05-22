"""Entrypoint for the standalone WhiteSnout Docker image.

Configuration is read from the ``WHITESNOUT_*`` environment variables (see
``whitesnout.config`` for the full list). The image sets reasonable defaults:

- ``WHITESNOUT_DIRECTORY=/srv``
- ``WHITESNOUT_SECURITY_HEADERS=true``
- ``WHITESNOUT_HEALTH_CHECK_PATH=/healthz``

Override any of them at ``docker run`` time with ``-e``.
"""

from __future__ import annotations

from whitesnout import WhiteSnout

app = WhiteSnout()
