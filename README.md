# whitesnout

[![tests](https://github.com/rrobles-qdq/whitesnout/actions/workflows/test.yml/badge.svg)](https://github.com/rrobles-qdq/whitesnout/actions/workflows/test.yml)
[![PyPI](https://img.shields.io/pypi/v/whitesnout.svg)](https://pypi.org/project/whitesnout/)
[![Python versions](https://img.shields.io/pypi/pyversions/whitesnout.svg)](https://pypi.org/project/whitesnout/)
[![codecov](https://codecov.io/gh/rrobles-qdq/whitesnout/branch/main/graph/badge.svg)](https://codecov.io/gh/rrobles-qdq/whitesnout)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**WhiteSnout** is an ASGI static file server for Python — like Whitenoise, but built for ASGI frameworks (FastAPI, Starlette, Django, etc.). It serves static files with minimal memory overhead, streaming content in chunks and leveraging pre-compressed assets. A Rust extension (PyO3) accelerates the hot path transparently.

---

## Quick start

```python
from whitesnout import WhiteSnout

# Standalone static file server
app = WhiteSnout(directory="./static")
```

Serve with any ASGI server:

```console
$ uvicorn myapp:app
```

### With FastAPI

```python
from fastapi import FastAPI
from whitesnout import WhiteSnout

api = FastAPI()

@api.get("/api")
def read_root():
    return {"hello": "world"}

app = WhiteSnout(api, directory="static")
```

Launch with uvicorn targeting the **WhiteSnout-wrapped** object:

```console
$ uvicorn main:app --reload --port 8000
```

> **Gotcha — do not use `fastapi dev` / `fastapi run`.** The FastAPI CLI auto-discovers the first `FastAPI` instance in the module and binds uvicorn to *it*, bypassing the WhiteSnout wrapper entirely. Static requests then hit FastAPI directly and return `{"detail":"Not Found"}`. Always launch via `uvicorn main:app` (or your ASGI server of choice) so the WhiteSnout instance handles the request. Same applies if you point at the inner FastAPI by name: `uvicorn main:api` skips WhiteSnout.

### With Django

```python
# asgi.py
import os
from django.core.asgi import get_asgi_application
from whitesnout import WhiteSnout

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")

django_app = get_asgi_application()
application = WhiteSnout(django_app, directory="static")
```

---

## Installation

```console
$ uv add whitesnout
```

Or with pip:

```console
$ pip install whitesnout
```

Requires Python **≥ 3.10**.

No required runtime dependencies. Optional extras:

```console
$ uv add 'whitesnout[compress]'   # Brotli for the compress CLI
$ uv add 'whitesnout[streaming]'  # aiofiles for non-blocking large-file streaming
```

### What `streaming` does

Files ≤ `sync_threshold` (default **64 KB**) are read in a single `asyncio.to_thread` call — no extra dependency needed. Covers ~95% of typical static assets (HTML, CSS, JS bundles, icons, fonts).

Files larger than `sync_threshold` are streamed in `chunk_size` (default 64 KB) pieces. Two backends are available:

- **Without `streaming` extra** (default): chunks are read via blocking `open()` inside the running event-loop task. Fine for low-concurrency workloads, but a slow disk read can stall other requests on the same worker.
- **With `streaming` extra**: chunks are read via `aiofiles`, which dispatches each read to a thread pool. Other requests keep progressing while the slow read happens.

**Install `[streaming]` when:**

- Serving files routinely larger than 64 KB (large JS bundles, videos, downloads, datasets)
- Running on slow / network-mounted disks (NFS, SMB, EBS gp2)
- High concurrency: many simultaneous large-file downloads

**Skip it when:**

- Only serving small assets (typical SPA build output, icons, fonts) — fast path already covers everything
- Raising `sync_threshold` to fit your largest expected file (e.g. `sync_threshold=2_000_000` for ≤ 2 MB)
- Memory-constrained environments — `aiofiles` adds ~500 KB resident

### Pre-compressing assets

Generate `.gz` and `.br` variants for all files in a directory:

```console
$ python -m whitesnout compress static/
Compressed: 42 gzip, 42 brotli
```

CLI flags:

| Flag | What it does |
|---|---|
| `--force` | Recompress even when the `.gz` / `.br` is newer than the source |
| `--include GLOB` | Only compress matching files. Repeatable (e.g. `--include "*.css" --include "*.js"`) |
| `--exclude GLOB` | Skip matching files. Repeatable |
| `--jobs N` / `-j N` | Worker processes (default: CPU count). Set `--jobs 1` for deterministic ordering |
| `--quiet` / `-q` | Suppress summary output |

This is a build-time step — at runtime WhiteSnout serves the pre-compressed files directly with zero CPU overhead. Common image, font, and archive extensions are skipped automatically (`.jpg`, `.png`, `.woff2`, `.zip`, …).

### Standalone server (`whitesnout serve`)

For quick local previews — no framework, no `uvicorn` invocation:

```console
$ python -m whitesnout serve ./static --port 8000
$ python -m whitesnout serve ./static --health-check-path /healthz \
    --request-id-header X-Request-ID
```

This wraps `uvicorn.run(WhiteSnout(directory=...))` with sensible defaults. Use it for demos, smoke tests, and the `--require-rust` path of CI. For production, run uvicorn directly with your own app so worker count, proxy headers, and graceful shutdown are explicit.

### Pre-flight (`whitesnout validate`)

Catch misconfigurations before deploy:

```console
$ python -m whitesnout validate ./static --manifest ./static/staticfiles.json
OK    directory: /app/static
OK    files: 142 regular files under directory
OK    brotli: importable
OK    rust extension: loaded
OK    manifest: ./static/staticfiles.json (142 entries)
```

Exit code is `1` if any `FAIL` line is printed. Flags `--require-brotli` and `--require-rust` upgrade the matching `WARN` to a `FAIL`.

---

## Configuration

All options can be passed as keyword arguments to `WhiteSnout`:

| Option | Default | Description |
|---|---|---|
| `app` | `None` | Inner ASGI app to fall through to when a file is not found |
| `directory` | `"static"` | Root directory to serve files from |
| `index_file` | `"index.html"` | File to serve for directory requests |
| `cache_max_age` | `3600` | `max-age` in `Cache-Control` for regular files |
| `immutable_max_age` | `31536000` | `max-age` for hashed files (1 year) |
| `immutable_pattern` | `r"\.[a-f0-9]{8,}\."` | Regex to detect hashed filenames (e.g. `styles.a1b2c3d4.css`) |
| `chunk_size` | `65536` | Stream chunk size in bytes (64 KB) |
| `sync_threshold` | `65536` | Read files ≤ this size in a single thread call (skips async generator) |
| `charset` | `"utf-8"` | Charset for text-based content types |
| `brotli` | `True` | Look for `.br` pre-compressed variants |
| `gzip` | `True` | Look for `.gz` pre-compressed variants |
| `max_cache_size` | `64` | Max entries in the native StatCache (stores `size, mtime_ns` tuples) |
| `cors` | `False` | Shortcut: add `Access-Control-Allow-Origin: *` (legacy; prefer `cors_allow_origins`) |
| `cors_allow_origins` | `None` | List of allowed origins (e.g. `["https://app.com"]` or `["*"]`); CORS preflight is handled accordingly; non-wildcard responses include `Vary: Origin` |
| `security_headers` | `True` | Add `X-Content-Type-Options: nosniff` and `X-Frame-Options: DENY` |
| `hsts` | `None` | `Strict-Transport-Security` header value (e.g. `"max-age=31536000; includeSubDomains"`) |
| `csp` | `None` | `Content-Security-Policy` header value |
| `referrer_policy` | `None` | `Referrer-Policy` header value (e.g. `"no-referrer"`) |
| `permissions_policy` | `None` | `Permissions-Policy` header value |
| `mime_types` | `None` | Dict of extension → MIME type overrides (e.g. `{".epub": "application/epub+zip"}`) |
| `skip_compress_extensions` | `{".jpg", ".png", ".gif", ...}` | Extensions excluded from on-the-fly compression |
| `manifest_path` | `None` | Path to a `staticfiles.json` / Webpack / Vite manifest; listed files are served as immutable |
| `autocompress` | `False` | On-the-fly gzip/brotli compression with in-memory LRU cache (per-process) |
| `autocompress_max_size` | `1_048_576` | Skip on-the-fly compression for files larger than this (bytes) |
| `on_request` | `None` | Callable (sync or async) invoked after every served request with a dict of metadata |
| `autorefresh` | `False` | Clear path and stat caches on every request (dev mode); auto-enabled by the Django wrapper when `settings.DEBUG` is True |
| `path_resolver` | `None` | Optional callable `(path: str) -> Path \| None` called when the standard resolution misses; used by the Django integration to plug `staticfiles.finders` |
| `health_check_path` | `None` | Path (e.g. `"/healthz"`) for a fixed `200 OK` reply with `Cache-Control: no-store`; bypasses the file pipeline |
| `request_id_header` | `None` | Header name (e.g. `"X-Request-ID"`) for per-request correlation; echoes incoming value or generates a UUID4 hex; exposed in `on_request` info as `request_id` |
| `error_responses` | `{404: b"Not Found", 405: b"Method Not Allowed", 416: b"Range Not Satisfiable"}` | Customize response bodies for error status codes; `{}` for empty bodies |
| `log_level` | `"INFO"` | Logging level (`"DEBUG"`, `"INFO"`, `"WARNING"`, etc.); `None` disables logging entirely |

```python
app = WhiteSnout(
    app=my_asgi_app,
    directory="public",
    cache_max_age=86400,
    immutable_max_age=31536000,
    chunk_size=131072,
)
```

---

## Features

- **ASGI-native** — middleware or standalone, works with any ASGI framework
- **Streaming** — files are served in configurable chunks (64 KB by default), never loaded entirely into memory
- **Zero-copy pre-compression** — serves pre-existing `.gz` and `.br` files with automatic `Accept-Encoding` negotiation; brotli preferred over gzip
- **On-the-fly compression** — opt-in `autocompress=True` compresses uncompressed assets on first request and caches the result in memory
- **Powerful caching** — `ETag`, `Last-Modified`, `Cache-Control`, `Vary: Accept-Encoding` headers; 304 Not Modified responses for conditional requests
- **Immutable cache** — detects hashed filenames via regex or a Django/Webpack/Vite manifest, then applies `Cache-Control: public, immutable, max-age=31536000`
- **Index files** — `index.html` served automatically for directory paths
- **Clean URLs** — `/dir` redirects to `/dir/` (301 Moved Permanently)
- **Path traversal protection** — resolved paths are verified to stay within the root directory
- **Low overhead** — LRU cache for file stats reduces `stat()` syscalls; no required runtime dependencies
- **MIME types** — content-type detection for 100+ file extensions with `mime_types={...}` overrides
- **Hardened security headers** — `HSTS`, `CSP`, `Referrer-Policy`, `Permissions-Policy` controllable via config
- **CORS allowlist** — `cors_allow_origins=[...]` matches per-request `Origin` and emits `Vary: Origin`
- **Observability hook** — `on_request=callable` is invoked after every served request with method/path/status/length/elapsed metadata
- **Compress CLI** — `python -m whitesnout compress <directory>` generates pre-compressed `.gz` and `.br` files as a build step
- **Rust extension** — `whitesnout._rs` speeds up the LRU cache, stat cache, response building, header parsing, and date comparison transparently; pure Python fallback when unavailable
- **Native StatCache** — stores `(size, mtime_ns)` as a Rust struct instead of Python `os.stat_result`, reducing GC pressure and memory overhead
- **Django integration** — `whitesnout.django.get_static_application()` wires Django ASGI + STATIC_ROOT + manifest in one call
- **Configurable error bodies** — customize 404/405/416 responses, or set `{}` for empty bodies
- **Silencable logging** — set `log_level=None` to disable all logging output
- **Multiple directories** — serve from additional directories and individual files via `add_directory()` / `add_files()` with runtime registration and removal
- **Multi-platform wheels** — pre-built for Linux (x86_64, arm64), macOS (x86_64, arm64), and Windows (amd64)

---

## Error responses

By default, whitesnout returns `404 Not Found`, `405 Method Not Allowed`, and `416 Range Not Satisfiable` with matching text bodies. Customize them via `error_responses`:

```python
app = WhiteSnout(
    directory="static",
    error_responses={404: b"File not found"},
)

# Empty bodies for all errors
app = WhiteSnout(directory="static", error_responses={})
```

When an inner ASGI app is configured, 404 and 405 errors are delegated to it instead.

---

## Logging

Request logging is enabled by default at `INFO` level. Control it via `log_level`:

```python
# Default INFO logging (method, path, status, bytes, duration)
app = WhiteSnout(directory="static")

# Custom level
app = WhiteSnout(directory="static", log_level="WARNING")

# Completely silent
app = WhiteSnout(directory="static", log_level=None)
```

---

## Multiple directories & extra files

Use `add_directory()` and `add_files()` to serve content from multiple locations:

```python
from fastapi import FastAPI
from whitesnout import WhiteSnout

app = FastAPI()

@app.get("/api/health")
def health():
    return {"status": "ok"}

ws = WhiteSnout(app, directory="frontend/dist")

# Extra directories
ws.add_directory("/media/uploads", "/mnt/storage/uploads")
ws.add_directory("/avatars", "/var/avatars")

# Individual files (take precedence over directories)
ws.add_files({
    "/.well-known/security.txt": "security/security.txt",
    "/favicon.ico": "branding/favicon.ico",
})

# Dynamic registrations at runtime
ws.remove_files("/favicon.ico")
ws.remove_directory("/avatars")
```

Resolution order: `add_files()` → `add_directory()` → main `directory` → inner ASGI app.

---

## Hardened security headers

Enable strict transport security, content security policy, referrer policy, and permissions policy via constructor kwargs. They are appended to every static response:

```python
app = WhiteSnout(
    directory="static",
    hsts="max-age=31536000; includeSubDomains; preload",
    csp="default-src 'self'; img-src 'self' data:",
    referrer_policy="strict-origin-when-cross-origin",
    permissions_policy="geolocation=(), camera=()",
)
```

`X-Content-Type-Options: nosniff` and `X-Frame-Options: DENY` are still controlled by `security_headers=True/False` (on by default).

---

## CORS allowlist

```python
# Whitelist specific origins (preferred). Each match returns Vary: Origin.
app = WhiteSnout(
    directory="static",
    cors_allow_origins=["https://app.example.com", "https://admin.example.com"],
)

# Wildcard (legacy behavior; same as cors=True)
app = WhiteSnout(directory="static", cors_allow_origins=["*"])
```

OPTIONS preflights are answered with 204 when the request origin matches. Unmatched origins return 405 (or fall through to your inner app if configured).

---

## Custom MIME types

Override or extend the built-in MIME table per instance:

```python
app = WhiteSnout(
    directory="static",
    mime_types={
        ".epub": "application/epub+zip",
        ".webmanifest": "application/manifest+json",
    },
)
```

The lookup runs after Rust derives the default content-type, so overrides win without sacrificing the hot path for everything else.

---

## Manifest-based immutable caching

Whitesnout reads three manifest formats out of the box. Listed files get `Cache-Control: public, immutable, max-age=31536000` regardless of the `immutable_pattern` regex.

```python
app = WhiteSnout(
    directory="static",
    manifest_path="static/staticfiles.json",  # Django, Webpack, or Vite
)
```

Supported shapes:

- **Django** `ManifestStaticFilesStorage` — `{"paths": {"app.css": "app.abc123.css"}}`
- **Webpack** — `{"app.js": "app.abc123.js"}`
- **Vite** — `{"src/main.ts": {"file": "assets/main.abc123.js"}}`

This handles modern bundlers' hashed filenames that don't match the default regex (e.g. `app-Abc123.js`).

---

## On-the-fly compression

Useful when running without a build-time compression step, or for dynamic directories where assets land at runtime:

```python
app = WhiteSnout(
    directory="static",
    autocompress=True,                    # opt-in
    autocompress_max_size=1_048_576,      # skip files > 1 MB
    skip_compress_extensions={
        ".jpg", ".png", ".webp", ".gz", ".br",
    },
)
```

The first request triggers compression in a background thread and caches the result in a bounded in-memory LRU (per process, keyed by `(path, mtime_ns, encoding)`). Subsequent requests for the same file serve the cached bytes. Pre-compressed `.gz` / `.br` files still win when they exist on disk — autocompress is the fallback.

Brotli requires `whitesnout[compress]` installed; without it, only gzip is used.

---

## Observability hook

```python
def on_request(info: dict) -> None:
    # info: method, path, status, length, elapsed_s, scope
    metrics.timing("whitesnout.request_ms", info["elapsed_s"] * 1000)
    metrics.incr(f"whitesnout.status.{info['status']}")

app = WhiteSnout(directory="static", on_request=on_request)
```

Async callables are awaited; exceptions raised by the hook are logged and swallowed so they never break a response. Use for OpenTelemetry spans, Prometheus counters, structured access logs, etc.

### OpenTelemetry helper

If you use OpenTelemetry, drop in the bundled adapter:

```python
from whitesnout import WhiteSnout
from whitesnout.otel import OpenTelemetryHook

hook = OpenTelemetryHook()  # uses the global tracer provider
app = WhiteSnout(directory="static", on_request=hook)
```

Each request becomes a span named `"{METHOD} {path}"` with HTTP semconv attributes (`http.request.method`, `http.response.status_code`, `http.response.body.size`, `url.path`). 5xx responses set the span status to `ERROR`. Pair with `opentelemetry-instrumentation-asgi` on the inner app to get a full trace tree. Optional dep: `opentelemetry-api`.

### Prometheus helper

If you use `prometheus-client`, drop in the bundled adapter:

```python
from prometheus_client import make_asgi_app
from whitesnout import WhiteSnout
from whitesnout.prometheus import PrometheusHook

hook = PrometheusHook()
app = WhiteSnout(directory="static", on_request=hook)
# Expose /metrics via prometheus_client.make_asgi_app() mounted on a sibling
# route in your framework (FastAPI, Starlette, Django).
```

Metrics emitted:

- `whitesnout_requests_total{method,status}` — counter
- `whitesnout_response_bytes_total{method}` — counter
- `whitesnout_request_duration_seconds{method,status}` — histogram

### Request-ID propagation

Pass `request_id_header="X-Request-ID"` and WhiteSnout will:

- Echo the incoming header value back on the response if present, or
- Generate a fresh UUID4 hex (32 chars, no dashes) when missing, and add it to the response.

The same value is exposed to `on_request` hooks via `info["request_id"]`, so structured loggers and tracing exporters can stitch every request together with the upstream proxy and downstream app:

```python
app = WhiteSnout(
    inner_app,
    directory="static",
    request_id_header="X-Request-ID",
    on_request=lambda info: logger.info(
        "static", extra={"request_id": info["request_id"], **info}
    ),
)
```

The same header name is used for both directions — if your reverse proxy already inserts `X-Request-Id`, WhiteSnout will pick it up, not double it.

### Health check endpoint

For load balancers and Kubernetes probes, set `health_check_path`. The reply is `200 OK` with `text/plain` body `OK` and `Cache-Control: no-store` — it bypasses the static file pipeline (no disk I/O, no cache lookups):

```python
app = WhiteSnout(directory="static", health_check_path="/healthz")
```

The check fires the `on_request` hook with status `200` like any other request, so it shows up in your metrics.

---

## Django integration

> Whitesnout is ASGI-native, so the Django integration only supports Django ASGI deployments (the `asgi.py` pattern). For Django WSGI / classic `runserver`, keep using `whitenoise`.

### `asgi.py` wrapper

```python
# asgi.py
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings")
django.setup()

from whitesnout.django import get_static_application
application = get_static_application()
```

`get_static_application()` reads:

- `STATIC_ROOT`         → `directory`
- `STATIC_URL`          → mount prefix when not `/static/`
- `STATICFILES_STORAGE` *or* `STORAGES["staticfiles"]["BACKEND"]` → if a Manifest storage is configured, hooks `static/staticfiles.json` automatically
- `DEBUG`               → if True and `autorefresh` is unset, enables `autorefresh=True`

Pass overrides through to `WhiteSnout`:

```python
application = get_static_application(
    hsts="max-age=31536000; includeSubDomains",
    cors_allow_origins=["https://app.example.com"],
)
```

### Development without `collectstatic`

```python
application = get_static_application(use_finders=True, autorefresh=True)
```

`use_finders=True` wires a `path_resolver` that calls `django.contrib.staticfiles.finders.find()` for every request that misses `STATIC_ROOT`. Combined with `autorefresh=True`, every request re-resolves and re-stats the file so edits show up immediately. Both options are typically gated by `settings.DEBUG`.

### `collectstatic` with compression in one step

Replace Django's default storage with whitesnout's compressed manifest storage to emit `.gz` + `.br` siblings during `manage.py collectstatic`. No separate build step needed.

```python
# settings.py (Django 4.2+)
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitesnout.storage.CompressedManifestStaticFilesStorage",
    },
}

# Django < 4.2
STATICFILES_STORAGE = "whitesnout.storage.CompressedManifestStaticFilesStorage"
```

Two variants are shipped:

- `whitesnout.storage.CompressedStaticFilesStorage` — no hashing, just gzip/brotli siblings
- `whitesnout.storage.CompressedManifestStaticFilesStorage` — Django's `ManifestStaticFilesStorage` + gzip/brotli (recommended for production)

Brotli output requires `whitesnout[compress]` installed in the build environment.

---

## Examples

End-to-end deployments live in [`examples/`](examples/):

- [`fastapi-spa/`](examples/fastapi-spa/) — FastAPI + Vite SPA with manifest, SPA fallback, hardened headers, autocompress
- [`django-asgi/`](examples/django-asgi/) — Django ASGI with `get_static_application()` + `CompressedManifestStaticFilesStorage` + dev mode (`use_finders` / `autorefresh`)
- [`starlette/`](examples/starlette/) — Starlette + multi-directory mount + `add_files` overrides + `on_request` observability hook
- [`litestar/`](examples/litestar/) — Litestar + Prometheus metrics + health endpoint + per-request correlation ID
- [`quart/`](examples/quart/) — Quart (async Flask) + on-the-fly compression + request-id propagation

Each example is self-contained — `cd` in, install requirements, `uvicorn` to run.

---

## Migration from Whitenoise

| Whitenoise option | Whitesnout equivalent |
|---|---|
| `WHITENOISE_ROOT` / `root=` | `directory=` |
| `WHITENOISE_USE_FINDERS` | Not applicable — point `directory=` at `STATIC_ROOT` after `collectstatic` |
| `WHITENOISE_MAX_AGE` | `cache_max_age=` |
| `WHITENOISE_IMMUTABLE_FILE_TEST` | `immutable_pattern=` + `manifest_path=` |
| `WHITENOISE_ALLOW_ALL_ORIGINS` | `cors_allow_origins=["*"]` (or `cors=True`) |
| `WHITENOISE_AUTOREFRESH` | `autorefresh=True` (auto-enabled by `whitesnout.django.get_static_application()` when `settings.DEBUG` is True) |
| `WHITENOISE_USE_FINDERS` | `get_static_application(use_finders=True)` |
| `CompressedManifestStaticFilesStorage` | `whitesnout.storage.CompressedManifestStaticFilesStorage` |
| `WHITENOISE_MIMETYPES` | `mime_types={...}` |
| `WHITENOISE_ADD_HEADERS_FUNCTION` | `on_request=callable` for observability; use `mime_types` + the security-header configs for static additions |
| `WHITENOISE_KEEP_ONLY_HASHED_FILES` | Handled by Django's `STATICFILES_STORAGE`; whitesnout reads the resulting manifest |
| `add_files()` (whitenoise) | `add_files({...})` |
| `WhiteNoise(application, root=...)` | `WhiteSnout(application, directory=...)` |

ASGI-specific: whitenoise is WSGI-only and must be wrapped in `WsgiToAsgi` when used with ASGI servers, paying the adapter cost on every request. Whitesnout is ASGI-native.

---

## Production deployment

WhiteSnout is a regular ASGI app. It does **not** open ports, terminate TLS, or spawn workers — that is the ASGI server's job. The recipe below is what we run in production.

### Behind a reverse proxy (recommended)

```
[client] -> [nginx / Caddy / Traefik] -> [uvicorn workers] -> [WhiteSnout]
```

The proxy terminates TLS, applies rate limits, and serves large static binaries (>10 MB) via `sendfile` if you point it at the same `static/` directory. WhiteSnout handles everything else — manifest-hashed assets, range requests, conditional GETs, on-the-fly compression, security headers.

Minimal `uvicorn` invocation:

```console
$ uvicorn myapp:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 4 \
    --proxy-headers \
    --forwarded-allow-ips='*' \
    --log-level warning
```

`--workers 4` matches roughly 2× CPU cores. WhiteSnout is async-safe with multiple workers — each worker has its own in-process cache, which is the trade-off you want (no shared-memory invalidation).

### Graceful shutdown

WhiteSnout handles ASGI **lifespan** events natively. When the host server starts draining (SIGTERM, `kubectl rollout`, etc.), WhiteSnout responds `lifespan.shutdown.complete` immediately — there is no background work, queue, or open connection to flush.

Pair with `uvicorn --timeout-graceful-shutdown 30` (default 30s) so in-flight requests finish before the worker exits.

### WebSockets

WhiteSnout does not serve WebSockets itself, but it transparently passes WebSocket scopes through to the inner ASGI app:

```python
from fastapi import FastAPI, WebSocket
from whitesnout import WhiteSnout

api = FastAPI()

@api.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_text("hi")

app = WhiteSnout(api, directory="static")
# /ws  -> handled by FastAPI
# /any.css -> handled by WhiteSnout
```

The HTTP path is the only one WhiteSnout intercepts. WebSocket, lifespan, and any other scope type goes straight to the inner app with no overhead.

### Kubernetes

Suggested probe config (assuming `health_check_path="/healthz"`):

```yaml
readinessProbe:
  httpGet:
    path: /healthz
    port: 8000
  periodSeconds: 5
  failureThreshold: 2
livenessProbe:
  httpGet:
    path: /healthz
    port: 8000
  periodSeconds: 10
  failureThreshold: 3
```

The endpoint is `Cache-Control: no-store` and bypasses the file pipeline, so probes never poison the cache.

### Docker

```dockerfile
FROM python:3.13-slim
WORKDIR /app
RUN pip install --no-cache-dir whitesnout uvicorn[standard]
COPY . .
CMD ["uvicorn", "myapp:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

WhiteSnout ships pre-compressed wheels for `manylinux_2_28_x86_64`, `aarch64`, macOS x86/arm, and Windows — no Rust toolchain needed inside the image. Wheels install in milliseconds.

---

## Performance tuning

Defaults are tuned for typical SPAs (small JS/CSS bundles, a few MB total). For larger asset sets, two knobs help:

| Knob | Default | When to change |
|---|---|---|
| `max_cache_size` | 64 | Set to roughly the count of unique URLs you serve. Hits stay in the path/stat cache; misses re-stat the FS. For 10k-file sites, 1024–4096. |
| `sync_threshold` | 65536 bytes (64 KiB) | Files at or below this size use a fast-path single `send()` (skips async generator overhead). Raise to 131072 if 95% of your assets are under 128 KiB and you have memory headroom; lower if you serve large media. |
| `chunk_size` | 65536 bytes | Stream chunk size for files above `sync_threshold`. Match this to your network MSS or the proxy buffer. Larger = fewer ASGI sends, higher RAM per request. |
| `autocompress` | `False` | Enable only when you cannot run `whitesnout compress dir/` ahead of time. Compression is cached in-memory by `(path, mtime, encoding)` — first request pays the CPU cost; the rest are free. |
| `autocompress_max_size` | 1 MiB | Cap on the source file size considered for on-the-fly compression. Large files should be pre-compressed. |

### Pre-compress over autocompress

`whitesnout compress static/` (or `CompressedManifestStaticFilesStorage` for Django) emits `.gz` and `.br` siblings at build time. Serving them is **zero CPU** at request time — WhiteSnout `stat`s the variant and sends it directly. `autocompress=True` is a fallback for dev or for files that change at runtime.

### Disable what you do not need

```python
app = WhiteSnout(
    directory="static",
    log_level=None,           # skip access-log formatting
    security_headers=False,   # if your reverse proxy emits them
    brotli=False,             # if you do not ship .br variants
)
```

`log_level=None` saves a `time.perf_counter()` call and the headers walk on every request. Worth it under heavy load if you log at the proxy.

### What the Rust hot path does

The Rust extension (`whitesnout._rs`) fuses `find_compressed` + `stat` + header construction into a single FFI call (`build_full_response_v2`). On a cache hit it returns roughly 1µs of headers; on a miss it returns ready-to-send bytes. If the extension is unavailable (no wheel for your arch), the Python fallback kicks in transparently — slower but functionally identical, exercised by `tests/test_fallbacks.py`.

---

## Architecture

```
whitesnout/
├── main.py              # ASGI middleware (always Python)
├── file_handler.py      # Path resolution, compression negotiation
├── response.py          # Header building, chunked streaming, 304
├── cache.py             # LRU cache (Python → falls back to Rust)
├── config.py            # Configuration dataclass
├── utils.py             # MIME type table, helpers
├── cli.py               # CLI entry point
├── compress.py          # Compression logic
├── manifest.py          # Django/Webpack/Vite manifest loader
├── autocompress.py      # In-memory LRU + gzip/brotli on-the-fly
├── django.py            # Django ASGI integration (get_static_application)
├── storage.py           # Django staticfiles storage backend (collectstatic + compress)
├── _rs.pyi              # Type stubs for the Rust extension
└── py.typed

examples/
├── fastapi-spa/         # FastAPI + Vite SPA
├── django-asgi/         # Django ASGI + collectstatic compress storage
└── starlette/           # Multi-directory + observability hook

whitesnout._rs           # Compiled Rust extension (PyO3)
├── LRUCache             # Generic LRU cache (O(1) via `lru` crate)
├── StatCache            # Native stat cache (stores size, mtime_ns without PyObject)
├── response             # compute_etag, format_last_modified, build_headers,
│                        # check_304, parse_range, build_content_range, etc.
├── utils                # guess_content_type (100+ MIME types)
└── file_handler         # find_compressed, parse_accept_encoding, is_hashed_file
```

The core logic consists of pure functions designed for gradual migration to Rust. The ASGI integration layer (`main.py`) stays in Python forever — it is the thin touchpoint with the ASGI protocol.

---

## Development

### With Docker (recommended)

```console
$ make build     # Build Docker image + compile Rust + install deps
$ make test      # Run test suite inside container
$ make shell     # Open interactive shell in container
$ make release   # Build release wheel
```

Requires Docker. The image is based on `rust:slim-trixie` with Python, uv, and maturin pre-installed.

### Without Docker

```console
$ uv sync --dev               # Install Python deps + build Rust extension
$ uv run pytest -v            # Run tests
$ maturin develop --uv        # Rebuild Rust extension only
```

Requires Rust (via rustup) and maturin (`cargo install maturin`).

---

## CHANGELOG

See [CHANGELOG.md](CHANGELOG.md) for the full release history.

---

## Benchmark

Results measured with `benchmarks/benchmark.py` (median of 15 runs) — 500 requests (10 concurrent) against uvicorn with a mix of static files (265 KB across 34 items) and a JSON API endpoint.

- **RPS** — Requests per second (higher is better)
- **P50** — Median latency in milliseconds (lower is better)
- **P99** — 99th percentile latency in milliseconds (lower is better)
- **RAM** — Resident set size in megabytes (lower is better)

| Server | RPS | P50 (ms) | P99 (ms) | RAM (MB) |
|---|---|---|---|---|
| **whitesnout** | **845** | 6.0 | 82.2 | 33.3 |
| whitenoise | 778 | 6.0 | 86.1 | 31.7 |

> **Platform**: Linux x86_64 (bare metal) · **Python**: 3.14.5 · **uvicorn**: 0.47.0 · WSGI bridge: `a2wsgi`
>
> Both servers run behind uvicorn for an apples-to-apples comparison. Whitenoise is WSGI-only, so it goes through `a2wsgi.WSGIMiddleware`; whitesnout speaks ASGI natively. Variance is ±10% on busy machines.

### nginx baseline (ceiling reference)

Both whitesnout and whitenoise are Python ASGI/WSGI servers — they cap out at roughly Python's request-handling rate. For honest context, run the nginx baseline (single-worker, sendfile-enabled) on the same machine:

```console
$ uv run python benchmarks/benchmark_nginx.py
```

nginx will typically land in the 10–20k RPS range on the same workload. Use it as a "what's the hardware ceiling?" reference, not a peer comparison — whitesnout's value is being part of your Python application process, not replacing a CDN edge.

### Running yourself

```console
$ uv run python benchmarks/benchmark.py          # whitesnout vs whitenoise
$ uv run python benchmarks/benchmark_nginx.py    # nginx ceiling (requires nginx on PATH)
```

---

## Stability & security

- [STABILITY.md](STABILITY.md) — versioning, deprecation policy, public API surface.
- [SECURITY.md](SECURITY.md) — vulnerability disclosure and supply-chain notes.

Releases land on PyPI via GitHub Actions Trusted Publishing (OIDC); wheels are
attested with `sigstore` and verifiable from the release artifacts.

---

## License

MIT — see [LICENSE](LICENSE) for the full text.
