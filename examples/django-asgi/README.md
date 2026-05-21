# Django ASGI + WhiteSnout

End-to-end example wiring whitesnout into a Django project's `asgi.py` and using `whitesnout.storage.CompressedManifestStaticFilesStorage` for `collectstatic`.

## Layout

```
django-asgi/
├── settings.py          # STORAGES uses whitesnout.storage
├── urls.py              # /api/health
├── asgi.py              # get_static_application()
├── assets/              # source static files (committed)
│   └── app.css
└── README.md
```

After `collectstatic`:

```
├── staticfiles/         # produced by collectstatic
│   ├── staticfiles.json # manifest (hashed names)
│   ├── app.abc12345.css
│   ├── app.abc12345.css.gz
│   └── app.abc12345.css.br
```

## Run

```console
$ uv add whitesnout django 'uvicorn[standard]' 'whitesnout[compress]'

# Development (no collectstatic needed)
$ DJANGO_DEBUG=1 uv run uvicorn asgi:application --port 8000

# Production
$ uv run python manage.py collectstatic --no-input
$ uv run uvicorn asgi:application --workers 4
```

## What this demonstrates

- **`get_static_application()`** wires Django ASGI + `STATIC_ROOT` + manifest in one call.
- **`CompressedManifestStaticFilesStorage`** hashes filenames *and* emits `.gz` + `.br` siblings during `collectstatic`. No separate compression step needed.
- **Dev mode**: `use_finders=True` resolves missing files via Django's staticfiles finders, so you can edit `assets/app.css` and reload without running `collectstatic`. `autorefresh=True` is auto-enabled by `settings.DEBUG`.
- **Hardened headers** and CORS allowlist enforced for every static response.

## Production checklist

- `DJANGO_DEBUG=0` (default) — disables autorefresh + use_finders for max throughput.
- Run `collectstatic` as a deploy step; storage backend handles hashing + compression.
- Cache `staticfiles/` between deploys for incremental compression (storage skips up-to-date `.gz`/`.br` files).
