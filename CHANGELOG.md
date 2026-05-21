# Changelog

## 1.0.0 (2026-05-21)

### Added

- **Environment variables** — all config options can be set via `WHITESNOUT_DIRECTORY`, `WHITESNOUT_CORS`, `WHITESNOUT_CACHE_MAX_AGE`, etc. Constructor kwargs take precedence over env vars
- **Async file IO** — `iter_chunks` uses `aiofiles` for non-blocking file reads; falls back to sync `open()` when `aiofiles` is not installed
- **Config tests** — 3 new tests covering env var override, kwarg precedence, and invalid value handling
- **Benchmark** — whitesnout 794 RPS vs whitenoise 829 RPS with comparable RAM

### Changed

- **`aiofiles`** — added as a core dependency (not optional)
- **Config** — all `__init__` params are now `None` by default, resolved via env → default chain
- **Logging** — request logging now includes duration in milliseconds

## 0.5.0 (2026-05-21)

### Added

- **CORS** — opt-in `cors=True` config adds `Access-Control-Allow-Origin: *` to all responses; handles OPTIONS preflight with 204
- **Logging** — request logging via `logging.getLogger("whitesnout")` logs method, path, status, bytes, and duration
- **Cache invalidation** — `WhiteSnout.invalidate_cache()` method to purge the stat cache programmatically
- **Tests** — 5 new tests covering CORS headers, preflight, disabled defaults, cache invalidation, and logging

### Added

- **Rust Phase 2** — `utils.py` (MIME types, `guess_content_type`) and `file_handler.py` (`find_compressed`, `parse_accept_encoding`, `is_hashed_file`) ported to Rust via PyO3
- **Expanded MIME types** — from 25 to 100+ entries covering web, images, fonts, documents, archives, audio, video, programming languages, and system formats
- **Rust unit tests** — `#[cfg(test)]` tests in `cache.rs`

### Changed

- **O(1) LRU cache** — replaced `Vec`-based O(n) implementation with the `lru` crate (`LruCache`) for constant-time get/put operations
- **Python fallback** — `utils.py` and `file_handler.py` try the Rust extension first, fall back to pure Python if unavailable
- **Benchmark updated** — whitesnout 859 RPS vs whitenoise 767 RPS (+12%) with similar RAM usage
- **Cargo dependencies** — added `regex` and `lru` crates

### Removed

- **Old Vec-based LRU** — removed custom O(n) LRU implementation from `src/cache.rs`

## 0.3.0 (2026-05-21)

### Added

- **Range Requests** — `Range: bytes=...` header parsed; returns 206 Partial Content with `Content-Range` and correct partial body; returns 416 Range Not Satisfiable for invalid ranges
- **Security headers** — `X-Content-Type-Options: nosniff` and `X-Frame-Options: DENY` added to all responses by default; controllable via `security_headers=False` option
- **Accept-Encoding quality values** — `parse_accept_encoding()` correctly sorts encodings by `q=` weight instead of naive substring match
- **Compression flags honored** — `find_compressed()` now respects `allow_brotli` and `allow_gzip` parameters from config
- **`security_headers()` response helper** — returns security header tuples based on config flag
- **`parse_range()` and `build_content_range()` helpers** — new pure functions for range request handling

### Changed

- **`iter_chunks()`** — now accepts optional `start` and `end` parameters for streaming partial content
- **`find_compressed()`** — uses quality-value-aware Accept-Encoding parsing
- **304 responses** — now include security headers when enabled
- **Config default** — `security_headers=True` by default

## 0.2.0 (2026-05-21)

### Added

- **Code quality tooling** — `ruff` (lint + format) and `ty` (type checker) added as dev dependencies; both run in CI to enforce code quality
- **ROADMAP** — added to README.md with planned versions up to v1.0.0
- **ASGI type aliases** — `ASGIApp`, `ASGISend`, `ASGIReceive` defined in `types.py` with zero runtime dependencies

### Changed

- **Type safety** — all modules now pass `ty check` with full type annotations; `app` and `send` parameters use proper ASGI protocol types instead of `object`
- **Config** — `immutable_pattern` stores a string instead of a compiled regex (simpler, same behavior)
- **Rust fallback** — `cache.py` constructor narrowed with explicit `ty: ignore` comments for the conditional import path
- **Formatting** — all source and test files formatted with `ruff format`

### Removed

- **mypy** — replaced by `ty` (Astral's type checker, same ecosystem as Ruff)

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
