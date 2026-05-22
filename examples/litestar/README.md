# Litestar + WhiteSnout

A minimal Litestar app served behind WhiteSnout. Demonstrates the integration pattern that mirrors FastAPI: WhiteSnout owns the static path; Litestar handles `/api/*`.

## Run

```console
$ pip install litestar uvicorn whitesnout prometheus-client
$ uvicorn main:app --port 8000
```

Then:

```console
$ curl -s -i http://localhost:8000/api/hello
$ curl -s -i http://localhost:8000/static/index.html
$ curl -s -i http://localhost:8000/healthz
```

## What this shows

- **Single ASGI mount**: WhiteSnout wraps Litestar. No middleware juggling.
- **Per-request correlation**: `request_id_header="X-Request-ID"` echoes any incoming ID and generates a UUID otherwise. The same ID is exposed to `on_request` hooks for log correlation.
- **Health endpoint**: `/healthz` returns `200 OK` directly, bypassing disk access.
- **Prometheus metrics**: `PrometheusHook` records counters and a duration histogram. Mount the `prometheus_client` ASGI app on `/metrics` from Litestar if you want HTTP scraping.

## Notes

- WhiteSnout intercepts **HTTP only**. WebSocket and lifespan scopes pass through to Litestar untouched.
- For SPA routing (HTML fallback), see [`../fastapi-spa/`](../fastapi-spa/) — the pattern carries over to Litestar verbatim.
