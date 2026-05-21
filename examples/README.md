# Examples

End-to-end deployments demonstrating whitesnout against the three most common ASGI frameworks.

| Directory | What it shows |
|---|---|
| [`fastapi-spa/`](fastapi-spa/) | FastAPI + Vite SPA with manifest-aware immutable caching, SPA fallback, hardened security headers, on-the-fly compression |
| [`django-asgi/`](django-asgi/) | Django ASGI via `get_static_application()` + `CompressedManifestStaticFilesStorage` + dev mode with `use_finders` / `autorefresh` |
| [`starlette/`](starlette/) | Starlette + multi-directory mount + `add_files` overrides + `on_request` observability hook |

Each example is self-contained: `cd` into the directory, install requirements, run uvicorn. Use them as starting points or as reference for production wiring.
