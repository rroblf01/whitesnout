"""Starlette + WhiteSnout with multiple directories and observability hook.

Run:

    uv run uvicorn main:app --port 8000
"""
from __future__ import annotations

import time
from pathlib import Path

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from whitesnout import WhiteSnout

BASE = Path(__file__).parent


async def homepage(request):
    return JSONResponse({"name": "demo", "static": "/static/app.css"})


async def health(request):
    return JSONResponse({"status": "ok"})


api = Starlette(
    routes=[
        Route("/", homepage),
        Route("/api/health", health),
    ]
)


def metrics_hook(info: dict) -> None:
    """Toy metrics sink. Replace with statsd / Prometheus / OTel in production."""
    print(
        f"[{info['status']}] {info['method']} {info['path']} "
        f"{info['length']} bytes {info['elapsed_s'] * 1000:.1f}ms"
    )


app = WhiteSnout(
    api,
    directory=str(BASE / "static"),
    on_request=metrics_hook,
    log_level=None,  # observability hook replaces logging
)

# Mount additional directories outside the project root
app.add_directory("/media", str(BASE / "uploads"))
app.add_files(
    {
        "/favicon.ico": str(BASE / "branding" / "favicon.ico"),
        "/robots.txt": str(BASE / "branding" / "robots.txt"),
    }
)
