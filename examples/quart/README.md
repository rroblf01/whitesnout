# Quart + WhiteSnout

Quart is the async port of Flask — speaks ASGI natively, so no WSGI bridge is needed. WhiteSnout wraps it the same way it wraps FastAPI/Litestar.

## Run

```console
$ pip install quart uvicorn whitesnout
$ uvicorn main:app --port 8000
```

Try it:

```console
$ curl -s http://localhost:8000/api/ping
$ curl -s http://localhost:8000/static/index.html
$ curl -s -i http://localhost:8000/healthz
```

## What this shows

- **Native ASGI integration**: Quart is one of the few WSGI-style frameworks that runs ASGI without an adapter. WhiteSnout's overhead per request is the same as with FastAPI or Starlette.
- **Autocompression**: `autocompress=True` gzips/brotlis assets on the first hit and caches the compressed bytes keyed by `(path, mtime, encoding)`. Skip it in production and pre-compress with `python -m whitesnout compress static/ --jobs=$(nproc)`.
- **Request correlation**: incoming `X-Request-ID` is echoed; missing ones get a UUID. Pair with a structured logger that picks up the same header on the Quart side.

## Migrating from Flask + Whitenoise

If you currently run `whitenoise` in a Flask app:

1. Switch the framework import from `flask` to `quart` (the public API is mostly compatible — `g`, `request`, blueprints, etc.).
2. Replace `WhiteNoise(app, root="static/")` with `WhiteSnout(app, directory="static")`.
3. Replace your WSGI server (`gunicorn flask_app:app`) with an ASGI one (`uvicorn quart_app:app`).

WhiteSnout is **not** a Flask drop-in — Flask is WSGI. Stick with Whitenoise there.
