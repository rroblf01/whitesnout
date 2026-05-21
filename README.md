# whitesnout

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

This is a build-time step — at runtime WhiteSnout serves the pre-compressed files directly with zero CPU overhead.

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

---

## Django integration

For `asgi.py` deployments:

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

- `STATIC_ROOT` → `directory`
- `STATIC_URL` → mount prefix when non-trivial
- `STATICFILES_STORAGE` → if a Manifest storage is configured, hooks `static/staticfiles.json` automatically

Pass overrides through to `WhiteSnout`:

```python
application = get_static_application(
    hsts="max-age=31536000; includeSubDomains",
    cors_allow_origins=["https://app.example.com"],
)
```

---

## Migration from Whitenoise

| Whitenoise option | Whitesnout equivalent |
|---|---|
| `WHITENOISE_ROOT` / `root=` | `directory=` |
| `WHITENOISE_USE_FINDERS` | Not applicable — point `directory=` at `STATIC_ROOT` after `collectstatic` |
| `WHITENOISE_MAX_AGE` | `cache_max_age=` |
| `WHITENOISE_IMMUTABLE_FILE_TEST` | `immutable_pattern=` + `manifest_path=` |
| `WHITENOISE_ALLOW_ALL_ORIGINS` | `cors_allow_origins=["*"]` (or `cors=True`) |
| `WHITENOISE_AUTOREFRESH` | Call `app.invalidate_cache()` after deploys; or use lower `max_cache_size` |
| `WHITENOISE_MIMETYPES` | `mime_types={...}` |
| `WHITENOISE_ADD_HEADERS_FUNCTION` | `on_request=callable` for observability; use `mime_types` + the security-header configs for static additions |
| `WHITENOISE_KEEP_ONLY_HASHED_FILES` | Handled by Django's `STATICFILES_STORAGE`; whitesnout reads the resulting manifest |
| `add_files()` (whitenoise) | `add_files({...})` |
| `WhiteNoise(application, root=...)` | `WhiteSnout(application, directory=...)` |

ASGI-specific: whitenoise is WSGI-only and must be wrapped in `WsgiToAsgi` when used with ASGI servers, paying the adapter cost on every request. Whitesnout is ASGI-native.

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
├── django.py            # Django ASGI integration
├── _rs.pyi              # Type stubs for the Rust extension
└── py.typed

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
| **whitesnout** | **856** | 6.0 | 80.0 | 33.0 |
| whitenoise | 907 | 5.8 | 81.3 | 31.5 |

> **Platform**: Linux x86_64 (bare metal) · **Python**: 3.14.5 · **uvicorn**: 0.47.0
>
> Bench variance is high (±10%) on busy machines; treat numbers as ballpark, not as a fine-grained ranking. The whitenoise side runs through `WsgiToAsgi`, which itself adds per-request overhead — whitesnout avoids that adapter entirely.

### Running yourself

```console
$ uv run python benchmarks/benchmark.py
```

---

---

## License

MIT — see [LICENSE](LICENSE) for the full text.
