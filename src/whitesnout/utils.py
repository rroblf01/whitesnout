from __future__ import annotations

_RUST_AVAILABLE = False

try:
    from whitesnout._rs import guess_content_type as _rs_guess_content_type

    _RUST_AVAILABLE = True
except ImportError:
    _rs_guess_content_type = None  # type: ignore[assignment]

MIME_TYPES: dict[str, str] = {
    ".html": "text/html",
    ".css": "text/css",
    ".js": "application/javascript",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
    ".eot": "application/vnd.ms-fontobject",
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".xml": "application/xml",
    ".zip": "application/zip",
    ".gz": "application/gzip",
    ".br": "application/brotli",
    ".map": "application/json",
    ".wasm": "application/wasm",
    ".mjs": "application/javascript",
    ".cjs": "application/javascript",
}


def guess_content_type(path: str, charset: str = "utf-8") -> str:
    if _RUST_AVAILABLE:
        return _rs_guess_content_type(path, charset)  # ty: ignore[call-non-callable]

    import os

    _ext = os.path.splitext(path)[1].lower()
    mime = MIME_TYPES.get(_ext, "application/octet-stream")
    if mime.startswith("text/") or mime in (
        "application/json",
        "application/javascript",
        "application/xml",
    ):
        mime = f"{mime}; charset={charset}"
    return mime
