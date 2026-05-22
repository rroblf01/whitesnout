"""Litestar + WhiteSnout — ASGI app with static asset serving.

Run::

    pip install litestar uvicorn whitesnout
    uvicorn main:app --port 8000

WhiteSnout wraps the Litestar app. Static asset requests under any path that
exists on disk under ``static/`` are served by WhiteSnout; everything else
falls through to Litestar.
"""

from __future__ import annotations

from litestar import Litestar, get
from whitesnout import WhiteSnout
from whitesnout.prometheus import PrometheusHook


@get("/api/hello")
async def hello() -> dict[str, str]:
    return {"hello": "litestar"}


api = Litestar(route_handlers=[hello])

app = WhiteSnout(
    api,
    directory="static",
    # Production-ish defaults
    security_headers=True,
    hsts="max-age=63072000; includeSubDomains",
    cache_max_age=3600,
    # Per-request correlation header — echoes if present, generates UUID otherwise
    request_id_header="X-Request-ID",
    # Health probe for k8s/load balancers; bypasses the file pipeline
    health_check_path="/healthz",
    # Observability — prometheus_client metrics under whitesnout_*
    on_request=PrometheusHook(),
)
