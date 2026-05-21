from __future__ import annotations

import email.utils
import os
from collections.abc import AsyncGenerator
from pathlib import Path

from whitesnout.config import Config


async def iter_chunks(
    path: Path,
    chunk_size: int,
    start: int = 0,
    end: int | None = None,
) -> AsyncGenerator[bytes, None]:
    with open(path, "rb") as f:
        if start:
            f.seek(start)
        remaining = None if end is None else (end - start + 1)
        while remaining is None or remaining > 0:
            to_read = chunk_size if remaining is None else min(chunk_size, remaining)
            chunk = f.read(to_read)
            if not chunk:
                break
            yield chunk
            if remaining is not None:
                remaining -= len(chunk)


def build_headers(
    *,
    content_type: str,
    content_length: int,
    extra: list[tuple[bytes, bytes]] | None = None,
) -> list[tuple[bytes, bytes]]:
    headers: list[tuple[bytes, bytes]] = [
        (b"content-type", content_type.encode()),
        (b"content-length", str(content_length).encode()),
    ]
    if extra:
        headers.extend(extra)
    return headers


async def send_response(
    send,
    status: int,
    headers: list[tuple[bytes, bytes]],
    body: bytes = b"",
) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": headers,
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": body,
            "more_body": False,
        }
    )


def security_headers(enabled: bool = True) -> list[tuple[bytes, bytes]]:
    if not enabled:
        return []
    return [
        (b"x-content-type-options", b"nosniff"),
        (b"x-frame-options", b"DENY"),
    ]


def not_found_headers() -> list[tuple[bytes, bytes]]:
    return [(b"content-type", b"text/plain; charset=utf-8")]


def method_not_allowed_headers() -> list[tuple[bytes, bytes]]:
    return [(b"content-type", b"text/plain; charset=utf-8")]


def redirect_headers(location: str) -> list[tuple[bytes, bytes]]:
    return [
        (b"location", location.encode()),
        (b"content-type", b"text/plain; charset=utf-8"),
    ]


def parse_range(range_header: str, file_size: int) -> tuple[int, int] | None:
    """Parse ``Range: bytes=start-end`` header.

    Returns (start, end) inclusive, or None if the range is invalid.
    """
    if not range_header.startswith("bytes="):
        return None
    try:
        range_val = range_header[6:].strip()
        if "-" not in range_val:
            return None
        start_str, end_str = range_val.split("-", 1)
        if start_str == "":
            # suffix range: -N → last N bytes
            n = int(end_str)
            return (max(0, file_size - n), file_size - 1) if n > 0 else None
        start = int(start_str)
        end = int(end_str) if end_str else file_size - 1
        if start < 0 or start >= file_size or end < start:
            return None
        return (start, min(end, file_size - 1))
    except (ValueError, TypeError):
        return None


def build_content_range(start: int, end: int, total: int) -> bytes:
    return f"bytes {start}-{end}/{total}".encode()


def compute_etag(st: os.stat_result) -> str:
    return f'"{st.st_mtime_ns:x}-{st.st_size:x}"'


def format_last_modified(st: os.stat_result) -> str:
    return email.utils.formatdate(st.st_mtime, usegmt=True)


def build_cache_control(config: Config, filename: str) -> str:
    from whitesnout.file_handler import is_hashed_file

    if is_hashed_file(filename, config.immutable_pattern):
        return f"public, immutable, max-age={config.immutable_max_age}"
    return f"public, max-age={config.cache_max_age}"


def check_304(
    request_headers: list[tuple[bytes, bytes]],
    etag: str,
    last_modified: str,
) -> bool:
    etag_match = None
    modified_since = None
    for name, value in request_headers:
        if name.lower() == b"if-none-match":
            etag_match = value.decode()
        elif name.lower() == b"if-modified-since":
            modified_since = value.decode()

    if etag_match is not None and (
        etag_match == "*" or etag in (etag_match, etag_match.strip('"'))
    ):
        return True

    if modified_since is not None:
        try:
            since_dt = email.utils.parsedate_to_datetime(modified_since)
            lm_dt = email.utils.parsedate_to_datetime(last_modified)
            if lm_dt is not None and since_dt is not None and lm_dt <= since_dt:
                return True
        except (ValueError, TypeError, OverflowError):
            pass

    return False
