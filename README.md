# whitesnout

**WhiteSnout** is an ASGI static file server for Python — like Whitenoise, but built for ASGI frameworks (FastAPI, Starlette, Django, etc.). It serves static files with minimal memory overhead, streaming content in chunks and leveraging pre-compressed assets.

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

Requires Python ≥ 3.14.

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

---

## Architecture

The library is structured for a future Rust rewrite of the hot path:

```
src/whitesnout/
├── main.py          # WhiteSnout ASGI middleware (thin integration layer)
├── file_handler.py  # Path resolution, compression negotiation (pure logic)
├── response.py      # Header building, chunked streaming, 304 handling
├── config.py        # Configuration dataclass
├── cache.py         # Generic LRU cache
└── utils.py         # MIME type table, helpers
```

The core logic in `file_handler.py` and `response.py` consists of pure functions with no side effects, making them straightforward to port to Rust while keeping the Python ASGI integration layer thin.

---

## License

MIT
