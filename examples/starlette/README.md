# Starlette + WhiteSnout

Demonstrates multi-directory serving, individual file overrides, and the `on_request` observability hook.

## Layout

```
starlette/
├── main.py
├── static/
│   └── app.css
├── uploads/             # served under /media/...
│   └── photo.jpg
├── branding/
│   ├── favicon.ico
│   └── robots.txt
└── README.md
```

## Routes

| URL | Source |
|---|---|
| `/` | Starlette JSON |
| `/api/health` | Starlette JSON |
| `/app.css` | `static/app.css` |
| `/media/photo.jpg` | `uploads/photo.jpg` (via `add_directory`) |
| `/favicon.ico` | `branding/favicon.ico` (via `add_files`) |
| `/robots.txt` | `branding/robots.txt` (via `add_files`) |

## Run

```console
$ uv add whitesnout starlette 'uvicorn[standard]'
$ uv run uvicorn main:app --port 8000
```

Every served request prints a single line via the `on_request` hook — replace with `statsd` / `prometheus_client` / `opentelemetry` exporters in production.

## Resolution order

`add_files()` → `add_directory()` → main `directory` → inner Starlette app. So `/favicon.ico` is overridden even if a file with that name lives under `static/`.
