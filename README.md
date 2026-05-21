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

The compress CLI needs Brotli:

```console
$ uv add 'whitesnout[compress]'
```

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
| `charset` | `"utf-8"` | Charset for text-based content types |
| `brotli` | `True` | Look for `.br` pre-compressed variants |
| `gzip` | `True` | Look for `.gz` pre-compressed variants |
| `max_cache_size` | `100` | Max entries in the native StatCache (stores `size, mtime_ns` tuples) |
| `cors` | `False` | Add `Access-Control-Allow-Origin: *` to all responses; handle OPTIONS preflight with 204 |
| `security_headers` | `True` | Add `X-Content-Type-Options: nosniff` and `X-Frame-Options: DENY` |
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
- **Powerful caching** — `ETag`, `Last-Modified`, `Cache-Control` headers; 304 Not Modified responses for conditional requests
- **Immutable cache** — detects hashed filenames (e.g. `app.abc12345.js`) and applies `Cache-Control: public, immutable, max-age=31536000`
- **Index files** — `index.html` served automatically for directory paths
- **Clean URLs** — `/dir` redirects to `/dir/` (301 Moved Permanently)
- **Path traversal protection** — resolved paths are verified to stay within the root directory
- **Low overhead** — LRU cache for file stats reduces `stat()` syscalls; no dependency bloat
- **MIME types** — content-type detection for 30+ file extensions, with automatic charset for text types
- **Compress CLI** — `python -m whitesnout compress <directory>` generates pre-compressed `.gz` and `.br` files as a build step
- **Rust extension** — `whitesnout._rs` speeds up the LRU cache, stat cache, response building, header parsing, and date comparison transparently; pure Python fallback when unavailable
- **Native StatCache** — stores `(size, mtime_ns)` as a Rust struct instead of Python `os.stat_result`, reducing GC pressure and memory overhead
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

Results measured with `benchmarks/benchmark.py` — 500 requests (10 concurrent) against uvicorn with a mix of static files (265 KB across 34 items) and a JSON API endpoint.

- **RPS** — Requests per second (higher is better)
- **P50** — Median latency in milliseconds (lower is better)
- **P99** — 99th percentile latency in milliseconds (lower is better)
- **RAM** — Resident set size in megabytes (lower is better)

| Server | RPS | P50 (ms) | P99 (ms) | RAM (MB) |
|---|---|---|---|---|
| **whitesnout** | **934** | 6.6 | 49.8 | 31.6 |
| whitenoise | 846 | 6.1 | 72.5 | 28.3 |

> **Platform**: Linux x86_64 · **Python**: 3.14.5 · **uvicorn**: 0.47.0

### Running yourself

```console
$ uv run python benchmarks/benchmark.py
```

---

---

## License

MIT — see [LICENSE](LICENSE) for the full text.
