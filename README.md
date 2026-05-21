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
| `max_cache_size` | `100` | Max entries in the LRU stat cache |

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
- **Rust extension** — `whitesnout._rs` speeds up the LRU cache transparently; pure Python fallback when unavailable
- **Multi-platform wheels** — pre-built for Linux (x86_64, arm64), macOS (x86_64, arm64), and Windows (amd64)

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
├── LRUCache             # Rust implementation, auto fallback to Python
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

### v0.2.0

| Server | RPS | P50 (ms) | P99 (ms) | RAM (MB) |
|---|---|---|---|---|
| **whitesnout** | 966 | 5.8 | 119.2 | 31.8 |
| whitenoise | 925 | 5.9 | 80.0 | 31.5 |

> **Platform**: Linux x86_64 · **Python**: 3.14.3 · **uvicorn**: 0.47.0

### Running yourself

```console
$ uv run python benchmarks/benchmark.py
```

---

## ROADMAP

```
v0.2.0 ─── Ruff + Ty + type safety (current)
v0.1.0 ─── Published
   │
   ├─ v0.2.0  Ruff + Ty + type safety
   ├─ v0.3.0  Range Requests + Security headers + Accept-Encoding quality values
   ├─ v0.4.0  Rust Phase 2 (utils, file_handler) + LRU cache O(1)
   ├─ v0.5.0  CORS + Logging + Cache invalidation
   └─ v1.0.0  Env vars + Async file IO + Benchmarks
```

### v0.2.0 — Ruff + Ty
- Add `ruff` (lint + format) and `ty` (type checker) for code validation
- Fix all lint/type errors; pass both in CI

### v0.3.0 — Range Requests & Security
- **Range Requests**: Parse `Range:` header, respond with `206 Partial Content` + `Content-Range`. Required for video, audio, and PDF seeking
- **Security headers**: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` by default
- **Accept-Encoding quality values**: Parse `Accept-Encoding: gzip, br;q=0.1` correctly instead of naive substring matching
- **Respect brotli/gzip flags**: `find_compressed` must skip `.br` when `brotli=False`

### v0.4.0 — Rust Phase 2 + LRU O(1)
- Port `utils.py` (MIME types) → `src/utils.rs`
- Port `file_handler.py` (find_compressed, is_hashed_file) → `src/file_handler.rs`
- Replace `Vec`-based Rust LRU with a `LinkedHashMap` for O(1) operations
- Add Rust unit tests (`#[cfg(test)]`)
- Expand MIME type table from 30 → 100+

### v0.5.0 — CORS, Logging & Cache invalidation
- **CORS opt-in**: Config `cors=True` → add `Access-Control-Allow-Origin: *`
- **Logging**: Basic request logging (method, path, status, bytes, duration)
- **Cache invalidation**: Programmatic `invalidate()` method to purge the LRU cache

### v1.0.0 — Production readiness
- **Environment variables**: `WHITESNOUT_DIRECTORY`, `WHITESNOUT_CACHE_MAX_AGE`, etc.
- **Async file IO**: Migrate `iter_chunks` to `anyio` or `aiofiles` to avoid blocking the event loop
- **Benchmarks**: Compare against Whitenoise and raw ASGI serving

---

## License

MIT — see [LICENSE](LICENSE) for the full text.
