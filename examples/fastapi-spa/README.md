# FastAPI + WhiteSnout (SPA)

End-to-end example serving a Single Page Application (React/Vue/Svelte) bundled by Vite, with a FastAPI JSON API alongside.

## Layout

```
fastapi-spa/
├── main.py            # FastAPI app + WhiteSnout
├── dist/              # SPA build output (gitignored; produced by `npm run build`)
│   ├── index.html
│   ├── assets/        # hashed JS/CSS
│   └── .vite/
│       └── manifest.json
└── README.md
```

## Run

```console
$ uv add whitesnout fastapi 'uvicorn[standard]'
$ uv run uvicorn main:app --port 8000
```

Visit:

- `http://localhost:8000/` — SPA entry
- `http://localhost:8000/api/health` — JSON from FastAPI
- `http://localhost:8000/assets/index-Abc123.js` — hashed bundle with `Cache-Control: public, immutable, max-age=31536000` (because manifest_path is configured)

## What this demonstrates

- **Manifest-aware immutability** — `dist/.vite/manifest.json` is read at startup; every file listed there gets the immutable cache header regardless of the regex pattern, so modern Vite hash schemes (`name-Abc123.js`) work out of the box.
- **SPA fallback** — non-file paths fall through to FastAPI's catch-all which returns `index.html`.
- **Hardened headers** — `hsts` and `csp` are sent on every response.
- **Autocompress** — when no pre-compressed `.gz`/`.br` is found, whitesnout compresses on the first request and caches the bytes.

## Production checklist

- Build the SPA: `npm run build`
- Generate pre-compressed siblings (optional, saves runtime CPU): `python -m whitesnout compress dist/`
- Run behind a real ASGI server: `uvicorn main:app --workers 4`
