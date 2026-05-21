from __future__ import annotations

_RUST_AVAILABLE = False

try:
    from whitesnout._rs import guess_content_type as _rs_guess_content_type

    _RUST_AVAILABLE = True
except ImportError:
    _rs_guess_content_type = None  # type: ignore[assignment]

MIME_TYPES: dict[str, str] = {
    # Web
    ".html": "text/html",
    ".htm": "text/html",
    ".css": "text/css",
    ".js": "application/javascript",
    ".mjs": "application/javascript",
    ".cjs": "application/javascript",
    ".jsx": "text/jsx",
    ".ts": "application/typescript",
    ".tsx": "text/typescript",
    ".json": "application/json",
    ".jsonld": "application/ld+json",
    ".xml": "application/xml",
    ".rss": "application/rss+xml",
    ".atom": "application/atom+xml",
    ".yaml": "application/yaml",
    ".yml": "application/yaml",
    ".wasm": "application/wasm",
    ".map": "application/json",
    # Images
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".bmp": "image/bmp",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
    ".avif": "image/avif",
    ".heic": "image/heic",
    ".heif": "image/heif",
    ".jp2": "image/jp2",
    ".jxr": "image/jxr",
    ".psd": "image/vnd.adobe.photoshop",
    ".ai": "application/postscript",
    ".eps": "application/postscript",
    # Fonts
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
    ".eot": "application/vnd.ms-fontobject",
    ".sfnt": "font/sfnt",
    # Documents
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".rtf": "application/rtf",
    ".csv": "text/csv",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument."
    "presentationml.presentation",
    ".odt": "application/vnd.oasis.opendocument.text",
    ".ods": "application/vnd.oasis.opendocument.spreadsheet",
    ".odp": "application/vnd.oasis.opendocument.presentation",
    # Archives / Compressed
    ".zip": "application/zip",
    ".gz": "application/gzip",
    ".br": "application/brotli",
    ".tar": "application/x-tar",
    ".tgz": "application/gzip",
    ".bz2": "application/x-bzip2",
    ".xz": "application/x-xz",
    ".zst": "application/zstd",
    ".7z": "application/x-7z-compressed",
    ".rar": "application/vnd.rar",
    # Audio
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
    ".aac": "audio/aac",
    ".wma": "audio/x-ms-wma",
    ".m4a": "audio/mp4",
    ".opus": "audio/opus",
    ".mid": "audio/midi",
    ".midi": "audio/midi",
    # Video
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".avi": "video/x-msvideo",
    ".mov": "video/quicktime",
    ".wmv": "video/x-ms-wmv",
    ".flv": "video/x-flv",
    ".mkv": "video/x-matroska",
    ".ogv": "video/ogg",
    ".m4v": "video/mp4",
    ".3gp": "video/3gpp",
    # Programming / Config
    ".py": "text/x-python",
    ".rb": "text/x-ruby",
    ".java": "text/x-java",
    ".go": "text/x-go",
    ".rs": "text/x-rust",
    ".sh": "application/x-sh",
    ".bash": "application/x-sh",
    ".zsh": "text/x-script.zsh",
    ".bat": "application/x-msdos-program",
    ".cmd": "application/x-msdos-program",
    ".ps1": "application/x-powershell",
    ".c": "text/x-c",
    ".cpp": "text/x-c++",
    ".cc": "text/x-c++",
    ".cxx": "text/x-c++",
    ".h": "text/x-c-header",
    ".hpp": "text/x-c++-header",
    ".php": "application/x-httpd-php",
    ".pl": "text/x-perl",
    ".swift": "text/x-swift",
    ".kt": "text/x-kotlin",
    ".kts": "text/x-kotlin",
    ".dart": "application/dart",
    ".lua": "text/x-lua",
    ".r": "text/x-r",
    ".sql": "application/sql",
    ".toml": "application/toml",
    ".ini": "text/plain",
    ".cfg": "text/plain",
    ".env": "text/plain",
    ".lock": "application/json",
    # Misc
    ".svgz": "image/svg+xml",
    ".swf": "application/x-shockwave-flash",
    ".manifest": "application/manifest+json",
    ".webmanifest": "application/manifest+json",
    ".apk": "application/vnd.android.package-archive",
    ".dmg": "application/x-apple-diskimage",
    ".iso": "application/x-iso9660-image",
    ".bin": "application/octet-stream",
    ".exe": "application/vnd.microsoft.portable-executable",
    ".dll": "application/x-msdownload",
    ".deb": "application/vnd.debian.binary-package",
    ".rpm": "application/x-rpm",
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
        "application/ld+json",
        "application/manifest+json",
        "application/rss+xml",
        "application/atom+xml",
    ):
        mime = f"{mime}; charset={charset}"
    return mime
