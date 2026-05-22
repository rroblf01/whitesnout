"""Quart + WhiteSnout — async Flask-style app with static asset serving.

Run::

    pip install quart uvicorn whitesnout
    uvicorn main:app --port 8000

Quart is ASGI-native (unlike Flask, which is WSGI). WhiteSnout sits in front,
serving anything under ``static/`` directly and forwarding API routes to Quart.
"""

from __future__ import annotations

from quart import Quart, jsonify
from whitesnout import WhiteSnout

api = Quart(__name__)


@api.route("/api/ping")
async def ping() -> dict[str, str]:
    return jsonify(status="ok")


app = WhiteSnout(
    api,
    directory="static",
    security_headers=True,
    request_id_header="X-Request-ID",
    health_check_path="/healthz",
    # Pre-compress static/* on disk for production. For dev, autocompress=True
    # gzips/brotlis on the fly (cached by (path, mtime, encoding)).
    autocompress=True,
)
