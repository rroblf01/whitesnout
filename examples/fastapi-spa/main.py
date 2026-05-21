"""FastAPI app with whitesnout serving an SPA build (React/Vue/Svelte etc.).

Run:

    uv run uvicorn main:app --reload

Frontend build output is expected at ./dist (Vite default). Routes:

- GET /api/health          -> JSON from FastAPI
- GET /api/items           -> JSON from FastAPI
- GET /assets/app.abc.js   -> served from ./dist/assets (immutable cache via manifest)
- GET /                    -> ./dist/index.html
- GET /any/other/path      -> ./dist/index.html (SPA fallback)
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from whitesnout import WhiteSnout

api = FastAPI(title="Items API")
DIST = Path(__file__).parent / "dist"


@api.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@api.get("/api/items")
def items() -> dict:
    return {"items": [{"id": 1, "name": "Alpha"}, {"id": 2, "name": "Beta"}]}


# SPA fallback: any non-API, non-file path returns index.html.
# Implemented as the inner ASGI app's catch-all; WhiteSnout matches files
# first, then falls through to this handler.
@api.get("/{full_path:path}")
def spa_index(full_path: str) -> dict:
    from fastapi.responses import FileResponse

    index = DIST / "index.html"
    if index.is_file():
        return FileResponse(str(index))
    return {"error": "build missing — run `npm run build` first"}


app = WhiteSnout(
    api,
    directory=str(DIST),
    manifest_path=str(DIST / ".vite" / "manifest.json"),  # Vite default location
    cors_allow_origins=["https://app.example.com"],
    hsts="max-age=31536000; includeSubDomains",
    csp="default-src 'self'; img-src 'self' data:",
    autocompress=True,
)
