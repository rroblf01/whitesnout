from __future__ import annotations

from collections.abc import Awaitable, Callable

ASGIReceive = Callable[[], Awaitable[dict]]
ASGISend = Callable[[dict], Awaitable[None]]
ASGIApp = Callable[[dict, ASGIReceive, ASGISend], Awaitable[None]]
