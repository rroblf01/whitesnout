# Changelog

## 2.0.0 (2026-05-21) — Performance, hardening, ecosystem

### Highlights

- 1 FFI call per request (compressed lookup + stat + headers fused into `build_full_response_v2`)
- No required Python runtime dependencies (`aiofiles` moved to the `[streaming]` extra)
- Native Rust StatCache + Rust hot path (multi-arch wheels via cibuildwheel)
- Whitenoise feature parity: Django integration, manifest support, on-the-fly compression, hardened security headers, CORS allowlist, observability hook
- 115 tests (was 93)

### Performance

- **Fused Rust pipeline** — `build_full_response_v2` in `src/response.rs` combines `find_compressed`, `stat` (via cache), 304 check, range handling and full header construction into one PyO3 call. Replaces three round-trips per request.
- **Fast-path send for small files** — files ≤ `sync_threshold` (default 64 KB) bypass the async generator entirely. Single `asyncio.to_thread` read + single `more_body=False` send.
- **Hand-written matcher for the default immutable pattern** — skips the `regex` engine when `immutable_pattern == r"\.[a-f0-9]{8,}\."`.
- **Lazy imports** — `aiofiles`, `email.utils`, `re`, `stat` now imported only when needed. Lower resident set at startup.
- **`Vary: Accept-Encoding`** added automatically when compression is on offer (correctness for HTTP caches).

### Features

- **`autocompress`** — opt-in on-the-fly gzip/brotli compression with bounded in-memory LRU cache (`whitesnout.autocompress`). Caches by `(path, mtime_ns, encoding)`. Honors `skip_compress_extensions` and `autocompress_max_size`.
- **`manifest_path`** — loader in `whitesnout.manifest` handles Django `ManifestStaticFilesStorage`, Webpack, and Vite manifest shapes. Listed files are served as immutable regardless of regex.
- **`mime_types`** — dict of extension → MIME type for per-instance overrides (e.g. `.epub`, `.webmanifest`).
- **`cors_allow_origins`** — list of allowed origins; non-wildcard matches emit `Vary: Origin`. OPTIONS preflight is gated by the allowlist.
- **`hsts`, `csp`, `referrer_policy`, `permissions_policy`** — config-driven hardening headers.
- **`on_request`** — sync or async callable invoked after every served request with method, path, status, length, elapsed time, and the raw scope. Exceptions are caught + logged.
- **`whitesnout.django`** — `get_static_application()` wires Django ASGI + STATIC_ROOT + manifest in one call.
- **`is_hashed_override`** parameter in the Rust pipeline lets the manifest force-flip cache-control without going through the regex.
- **Type stubs** — new `_rs.pyi` covers the Rust extension surface for IDE completion.
- **`skip_compress_extensions`** — set of extensions excluded from on-the-fly compression.
- **`autocompress_max_size`** — guard against compressing very large files (default 1 MB).
- **Env vars** — `WHITESNOUT_CORS_ALLOW_ORIGINS`, `WHITESNOUT_HSTS`, `WHITESNOUT_CSP`, `WHITESNOUT_REFERRER_POLICY`, `WHITESNOUT_PERMISSIONS_POLICY`, `WHITESNOUT_FORCE_TEXT_EXTENSIONS`, `WHITESNOUT_SKIP_COMPRESS_EXTENSIONS`, `WHITESNOUT_MANIFEST_PATH`, `WHITESNOUT_AUTOCOMPRESS`, `WHITESNOUT_AUTOCOMPRESS_MAX_SIZE`.

### Changed

- **`aiofiles` is now an extra** — install `whitesnout[streaming]` if you serve files larger than `sync_threshold`. Default sync threshold covers the vast majority of static-asset workloads.
- **Default `cors=True` behavior** — internally translates to `cors_allow_origins=["*"]`. New code should set `cors_allow_origins` directly.
- **Rust `build_full_response_v2`** — new arguments `is_hashed_override: Option<bool>` and `add_vary: bool`.
- **StatCache impl reference** cached on `WhiteSnout` to skip one attribute lookup per request.
- **Scope `method` and `path`** read once, reused locally — fewer dict lookups in the hot path.
- **Logging** uses `logger.isEnabledFor(INFO)` to skip formatting when disabled.

### Internal

- New modules: `whitesnout.manifest`, `whitesnout.autocompress`, `whitesnout.django`.
- New tests: `tests/test_v2_features.py` — 22 cases covering Vary, CORS allowlist, security headers, MIME overrides, manifest formats, autocompress LRU, observability hooks, env vars.
- Hand-written hashed-filename matcher in `src/response.rs`.

### Migration notes

- `cors=True` still works but `cors_allow_origins=["..."]` is the recommended form for production.
- Apps relying on `aiofiles` should install `whitesnout[streaming]`; otherwise iter_chunks falls back to blocking `open()` for files larger than `sync_threshold`.
- Custom `STATICFILES_STORAGE` users should set `manifest_path` for precise immutable detection — the default regex still works for filenames matching `\.[a-f0-9]{8,}\.`.

### Benchmark

500 requests, 10 concurrent, mixed asset workload (median of 15 runs, bare metal):

| Server | RPS | P50 (ms) | P99 (ms) | RAM (MB) |
|---|---|---|---|---|
| **whitesnout** | **845** | 6.0 | 82.2 | 33.3 |
| whitenoise | 778 | 6.0 | 86.1 | 31.7 |

Whitenoise runs behind `a2wsgi.WSGIMiddleware` because it is WSGI-only; whitesnout is ASGI-native. Median of 15 runs.

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
