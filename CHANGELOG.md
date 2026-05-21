# Changelog

## [0.1.1](https://github.com/rroblf01/whitesnout/compare/v0.1.0...v0.1.1) (2026-05-21)


### Bug Fixes

* add x86_64-apple-darwin Rust target for macOS cross-compilation ([c68642a](https://github.com/rroblf01/whitesnout/commit/c68642a8fc5e6c5b42c9af535ba388ffe805e7ef))

## 0.1.0 (2026-05-21)

### Added

- **ASGI static file server** — `WhiteSnout` class that serves static files from a directory, works as standalone or wrapping any ASGI app (FastAPI, Django, Starlette, etc.)
- **Streaming** — files are served in configurable 64 KB chunks; never loaded entirely into memory
- **MIME type detection** — 30+ file extensions with automatic charset for text types
- **HTTP caching** — `ETag` (mtime+size based), `Last-Modified`, `Cache-Control` headers
- **Conditional requests** — 304 Not Modified responses for `If-None-Match` and `If-Modified-Since`
- **Pre-compressed files** — serves `.gz` and `.br` variants based on `Accept-Encoding`; Brotli preferred over Gzip
- **Index files** — automatically serves `index.html` for directory paths
- **Clean URLs** — redirects `/dir` to `/dir/` (301 Moved Permanently)
- **Immutable cache** — detects hashed filenames (e.g. `styles.a1b2c3d4.css`) and applies `Cache-Control: public, immutable, max-age=31536000`
- **LRU stat cache** — caches `stat()` results to reduce syscalls on frequently requested files
- **Path traversal protection** — resolves and verifies all paths stay within the root directory
- **Compress CLI** — `python -m whitesnout compress <directory>` generates pre-compressed `.gz` and `.br` files; skips up-to-date files unless `--force` is used
- **Python 3.10–3.14 support** — verified with CI matrix across all five versions
- **GitHub Actions CI** — matrix testing across Python 3.10–3.14, multi-platform wheel publishing to PyPI via cibuildwheel
- **Dockerfile** — `rust:slim-trixie` with Python, uv, and maturin for Rust/PyO3 development
- **Makefile** — targets for `build`, `test`, `shell`, `release`, and `clean`
- **Rust/PyO3 extension** — `whitesnout._rs` compiled submodule with LRU cache in Rust; automatic fallback to pure Python when unavailable
- **Optional Brotli dependency** — `uv add whitesnout[compress]` enables Brotli compression in the CLI

### Architecture

```
whitesnout/
├── main.py          # ASGI middleware (always Python — thin integration layer)
├── file_handler.py  # Pure functions (→ migratable to Rust)
├── response.py      # Pure functions (→ migratable to Rust)
├── utils.py         # Pure functions (→ migratable to Rust)
├── cache.py         # Python LRU with Rust fallback via whitesnout._rs
├── config.py        # Configuration dataclass
├── cli.py           # CLI entry point
├── compress.py      # Compression logic
└── py.typed

whitesnout._rs       # Compiled Rust extension (PyO3)
├── LRUCache         # Rust implementation, fallback to Python if unavailable
```

The core logic consists of pure functions with no side effects, designed for gradual migration to Rust while keeping the ASGI integration layer in Python.
