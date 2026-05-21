from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path

from whitesnout.config import Config

_RUST_AVAILABLE = False

try:
    from whitesnout._rs import (
        build_all_headers as _rs_build_all_headers,
    )
    from whitesnout._rs import (
        build_cache_control as _rs_build_cache_control,
    )
    from whitesnout._rs import (
        build_content_range as _rs_build_content_range,
    )
    from whitesnout._rs import (
        build_full_response as _rs_build_full_response,
    )
    from whitesnout._rs import (
        build_full_response_v2 as _rs_build_full_response_v2,
    )
    from whitesnout._rs import (
        build_headers as _rs_build_headers,
    )
    from whitesnout._rs import (
        check_304 as _rs_check_304,
    )
    from whitesnout._rs import (
        compute_etag as _rs_compute_etag,
    )
    from whitesnout._rs import (
        format_last_modified as _rs_format_last_modified,
    )
    from whitesnout._rs import (
        parse_range as _rs_parse_range,
    )
    from whitesnout._rs import (
        security_headers as _rs_security_headers,
    )

    _RUST_AVAILABLE = True
except ImportError:
    pass

_aiofiles = None
_aiofiles_checked = False


def _get_aiofiles():
    global _aiofiles, _aiofiles_checked
    if not _aiofiles_checked:
        _aiofiles_checked = True
        try:
            import aiofiles as _aio  # type: ignore[import-not-found]

            _aiofiles = _aio
        except ImportError:
            _aiofiles = None
    return _aiofiles


async def iter_chunks(
    path: Path,
    chunk_size: int,
    start: int = 0,
    end: int | None = None,
    sync_threshold: int = 0,
    file_size: int | None = None,
) -> AsyncGenerator[bytes, None]:
    remaining = None if end is None else (end - start + 1)
    total_size = remaining if remaining is not None else file_size
    # Fast path: read small files in one shot via thread (avoids aiofiles overhead)
    if total_size is not None and total_size <= sync_threshold:

        def _read() -> bytes:
            with open(path, "rb") as f:
                if start:
                    f.seek(start)
                if remaining is not None:
                    return f.read(remaining)
                return f.read()

        yield await asyncio.to_thread(_read)
        return

    aio = _get_aiofiles()
    if aio is not None:
        async with aio.open(path, "rb") as f:
            if start:
                await f.seek(start)
            while remaining is None or remaining > 0:
                to_read = (
                    chunk_size if remaining is None else min(chunk_size, remaining)
                )
                chunk = await f.read(to_read)
                if not chunk:
                    break
                yield chunk
                if remaining is not None:
                    remaining -= len(chunk)
    else:
        with open(path, "rb") as f:
            if start:
                f.seek(start)
            while remaining is None or remaining > 0:
                to_read = (
                    chunk_size if remaining is None else min(chunk_size, remaining)
                )
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
    if _RUST_AVAILABLE:
        extra_str = [(k.decode(), v.decode()) for k, v in (extra or [])]
        result = _rs_build_headers(content_type, content_length, extra_str)
        return [(k.encode(), v.encode()) for k, v in result]
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
    if _RUST_AVAILABLE:
        result = _rs_security_headers(enabled)
        return [(k.encode(), v.encode()) for k, v in result]
    if not enabled:
        return []
    return [
        (b"x-content-type-options", b"nosniff"),
        (b"x-frame-options", b"DENY"),
    ]


def error_headers(
    status: int,
    body: bytes | None,
    error_responses: dict[int, bytes],
) -> list[tuple[bytes, bytes]]:
    if status in (301,):
        return [(b"content-type", b"text/plain; charset=utf-8")]
    content = body if body is not None else error_responses.get(status, b"")
    ct = b"text/plain; charset=utf-8" if content else b""
    return [(b"content-type", ct)] if ct else []


def redirect_headers(location: str) -> list[tuple[bytes, bytes]]:
    return [
        (b"location", location.encode()),
        (b"content-type", b"text/plain; charset=utf-8"),
    ]


def parse_range(range_header: str, file_size: int) -> tuple[int, int] | None:
    if _RUST_AVAILABLE:
        return _rs_parse_range(range_header, file_size)
    if not range_header.startswith("bytes="):
        return None
    try:
        range_val = range_header[6:].strip()
        if "-" not in range_val:
            return None
        start_str, end_str = range_val.split("-", 1)
        if start_str == "":
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
    if _RUST_AVAILABLE:
        return _rs_build_content_range(start, end, total).encode()
    return f"bytes {start}-{end}/{total}".encode()


def compute_etag(size: int, mtime_ns: int) -> str:
    if _RUST_AVAILABLE:
        return _rs_compute_etag(size, mtime_ns)
    return f'"{mtime_ns:x}-{size:x}"'


def format_last_modified(mtime_ns: int) -> str:
    if _RUST_AVAILABLE:
        return _rs_format_last_modified(mtime_ns)
    import email.utils as _eu

    return _eu.formatdate(mtime_ns / 1_000_000_000, usegmt=True)


def build_cache_control(config: Config, filename: str) -> str:
    from whitesnout.file_handler import is_hashed_file

    is_hashed = is_hashed_file(filename, config.immutable_pattern)
    if _RUST_AVAILABLE:
        return _rs_build_cache_control(
            is_hashed,
            config.cache_max_age,
            config.immutable_max_age,
        )
    if is_hashed:
        return f"public, immutable, max-age={config.immutable_max_age}"
    return f"public, max-age={config.cache_max_age}"


def build_all_headers(
    content_type: str,
    content_length: int,
    etag: str,
    last_modified: str,
    cache_control: str,
    content_encoding: str | None = None,
    security_enabled: bool = True,
    cors_enabled: bool = False,
    range_header: str | None = None,
    file_size: int = 0,
) -> tuple[list[tuple[bytes, bytes]], int, int, tuple[int, int] | None]:
    if _RUST_AVAILABLE:
        raw = _rs_build_all_headers(
            content_type,
            content_length,
            etag,
            last_modified,
            cache_control,
            content_encoding,
            security_enabled,
            cors_enabled,
            range_header,
            file_size,
        )
        raw_headers, status, final_length, raw_range = raw
        headers: list[tuple[bytes, bytes]] = [
            (hname, hval) for hname, hval in raw_headers
        ]
        return (headers, status, final_length, raw_range)
    headers: list[tuple[bytes, bytes]] = [
        (b"content-type", content_type.encode()),
        (b"content-length", str(content_length).encode()),
        (b"etag", etag.encode()),
        (b"last-modified", last_modified.encode()),
        (b"cache-control", cache_control.encode()),
    ]
    if security_enabled:
        headers.append((b"x-content-type-options", b"nosniff"))
        headers.append((b"x-frame-options", b"DENY"))
    if cors_enabled:
        headers.append((b"access-control-allow-origin", b"*"))
    if content_encoding:
        headers.append((b"content-encoding", content_encoding.encode()))
    status = 200
    final_length = content_length
    range_spec: tuple[int, int] | None = None
    if range_header:
        parsed = parse_range(range_header, file_size)
        if parsed is not None:
            rstart, rend = parsed
            status = 206
            final_length = rend - rstart + 1
            cr = build_content_range(rstart, rend, file_size)
            headers.append((b"content-range", cr))
            range_spec = (rstart, rend)
    return (headers, status, final_length, range_spec)


_content_type_cache: dict[str, str] = {}


def build_full_response(
    file_size: int,
    mtime_ns: int,
    filename: str,
    charset: str = "utf-8",
    cache_max_age: int = 3600,
    immutable_max_age: int = 31536000,
    immutable_pattern: str = "",
    content_encoding: str | None = None,
    security_enabled: bool = True,
    cors_enabled: bool = False,
    range_header: str | None = None,
    method: str = "GET",
    if_none_match: str | None = None,
    if_modified_since: str | None = None,
    file_path_str: str = "",
) -> tuple[list[tuple[bytes, bytes]], int, int, tuple[int, int] | None, bool]:
    if _RUST_AVAILABLE:
        raw = _rs_build_full_response(
            file_size,
            mtime_ns,
            filename,
            charset,
            cache_max_age,
            immutable_max_age,
            immutable_pattern,
            content_encoding,
            security_enabled,
            cors_enabled,
            range_header,
            method,
            if_none_match,
            if_modified_since,
            file_path_str,
        )
        raw_headers, status, final_length, raw_range, is_304 = raw
        headers: list[tuple[bytes, bytes]] = [
            (hname, hval) for hname, hval in raw_headers
        ]
        return (headers, status, final_length, raw_range, is_304)

    # Python fallback
    etag = compute_etag(file_size, mtime_ns)
    last_modified = format_last_modified(mtime_ns)
    from whitesnout.file_handler import is_hashed_file

    is_hashed = is_hashed_file(filename, immutable_pattern)
    if is_hashed:
        cache_control = f"public, immutable, max-age={immutable_max_age}"
    else:
        cache_control = f"public, max-age={cache_max_age}"

    from whitesnout.utils import guess_content_type

    if file_path_str:
        ext = file_path_str.rsplit(".", 1)[-1] if "." in file_path_str else ""
        ct = _content_type_cache.get(ext)
        if ct is None:
            ct = guess_content_type(file_path_str, charset)
            _content_type_cache[ext] = ct
        content_type = ct
    else:
        content_type = guess_content_type(filename, charset)

    # 304 check
    if if_none_match is not None:
        em = if_none_match.strip()
        if em == "*" or em.strip('"') == etag.strip('"'):
            headers = [
                (b"etag", etag.encode()),
                (b"last-modified", last_modified.encode()),
                (b"cache-control", cache_control.encode()),
            ]
            if security_enabled:
                headers.extend(
                    [
                        (b"x-content-type-options", b"nosniff"),
                        (b"x-frame-options", b"DENY"),
                    ]
                )
            if cors_enabled:
                headers.append((b"access-control-allow-origin", b"*"))
            return (headers, 304, 0, None, True)

    if if_modified_since is not None:
        try:
            import email.utils as _eu  # noqa: PLC0415

            since_dt = _eu.parsedate_to_datetime(if_modified_since)
            lm_dt = _eu.parsedate_to_datetime(last_modified)
            if lm_dt is not None and since_dt is not None and lm_dt <= since_dt:
                headers = [
                    (b"etag", etag.encode()),
                    (b"last-modified", last_modified.encode()),
                    (b"cache-control", cache_control.encode()),
                ]
                if security_enabled:
                    headers.extend(
                        [
                            (b"x-content-type-options", b"nosniff"),
                            (b"x-frame-options", b"DENY"),
                        ]
                    )
                if cors_enabled:
                    headers.append((b"access-control-allow-origin", b"*"))
                return (headers, 304, 0, None, True)
        except (ValueError, TypeError, OverflowError):
            pass

    headers = [
        (b"content-type", content_type.encode()),
        (b"content-length", str(file_size).encode()),
        (b"etag", etag.encode()),
        (b"last-modified", last_modified.encode()),
        (b"cache-control", cache_control.encode()),
    ]
    if security_enabled:
        headers.extend(
            [(b"x-content-type-options", b"nosniff"), (b"x-frame-options", b"DENY")]
        )
    if cors_enabled:
        headers.append((b"access-control-allow-origin", b"*"))
    if content_encoding:
        headers.append((b"content-encoding", content_encoding.encode()))

    status = 200
    final_length = file_size
    range_spec: tuple[int, int] | None = None

    if method == "GET" and range_header:
        parsed = parse_range(range_header, file_size)
        if parsed is not None:
            rstart, rend = parsed
            status = 206
            final_length = rend - rstart + 1
            cr = build_content_range(rstart, rend, file_size)
            headers.append((b"content-range", cr))
            range_spec = (rstart, rend)

    return (headers, status, final_length, range_spec, False)


def build_response_pipeline(
    file_path: Path,
    stat_cache_impl,
    accept_encoding: str,
    *,
    allow_brotli: bool,
    allow_gzip: bool,
    filename: str,
    charset: str,
    cache_max_age: int,
    immutable_max_age: int,
    immutable_pattern: str,
    security_enabled: bool,
    cors_enabled: bool,
    range_header: str | None,
    method: str,
    if_none_match: str | None,
    if_modified_since: str | None,
    is_hashed_override: bool | None = None,
    add_vary: bool = True,
) -> tuple[
    Path, list[tuple[bytes, bytes]], int, int, tuple[int, int] | None, bool, str | None
]:
    file_path_str = str(file_path)
    if _RUST_AVAILABLE:
        try:
            from whitesnout._rs import (
                StatCache as _RustStatCache,  # noqa: N806
            )
        except ImportError:
            _RustStatCache = None  # type: ignore # noqa: N806

        if _RustStatCache is not None and isinstance(stat_cache_impl, _RustStatCache):
            (
                serve_path_str,
                raw_headers,
                status,
                content_length,
                range_spec,
                is_304,
                _content_encoding,
            ) = _rs_build_full_response_v2(
                file_path_str,
                stat_cache_impl,
                accept_encoding,
                allow_brotli,
                allow_gzip,
                filename,
                charset,
                cache_max_age,
                immutable_max_age,
                immutable_pattern,
                security_enabled,
                cors_enabled,
                range_header,
                method,
                if_none_match,
                if_modified_since,
                is_hashed_override,
                add_vary,
            )
            serve_path = (
                file_path if serve_path_str == file_path_str else Path(serve_path_str)
            )
            headers: list[tuple[bytes, bytes]] = list(raw_headers)
            return (
                serve_path,
                headers,
                status,
                content_length,
                range_spec,
                is_304,
                _content_encoding,
            )

    # Python / non-fused fallback
    from whitesnout.file_handler import find_compressed

    compressed = find_compressed(
        file_path,
        accept_encoding,
        allow_brotli=allow_brotli,
        allow_gzip=allow_gzip,
    )
    if compressed is not None:
        serve_path, content_encoding = compressed
    else:
        serve_path = file_path
        content_encoding = None

    cache_key = str(serve_path)
    cached = stat_cache_impl.get(cache_key)
    if cached is not None:
        file_size, mtime_ns = cached
    else:
        st = serve_path.stat()
        file_size, mtime_ns = st.st_size, st.st_mtime_ns
        stat_cache_impl.put(cache_key, file_size, mtime_ns)

    headers, status, content_length, range_spec, is_304 = build_full_response(
        file_size=file_size,
        mtime_ns=mtime_ns,
        filename=filename,
        charset=charset,
        cache_max_age=cache_max_age,
        immutable_max_age=immutable_max_age,
        immutable_pattern=immutable_pattern,
        content_encoding=content_encoding,
        security_enabled=security_enabled,
        cors_enabled=cors_enabled,
        range_header=range_header,
        method=method,
        if_none_match=if_none_match,
        if_modified_since=if_modified_since,
        file_path_str=file_path_str,
    )
    return (
        serve_path,
        headers,
        status,
        content_length,
        range_spec,
        is_304,
        content_encoding,
    )


def check_304(
    request_headers: list[tuple[bytes, bytes]],
    etag: str,
    last_modified: str,
) -> bool:
    if _RUST_AVAILABLE:
        etag_match = None
        modified_since = None
        for name, value in request_headers:
            if name.lower() == b"if-none-match":
                etag_match = value.decode()
            elif name.lower() == b"if-modified-since":
                modified_since = value.decode()
        return _rs_check_304(etag_match, modified_since, etag, last_modified)

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
            import email.utils as _eu  # noqa: PLC0415

            since_dt = _eu.parsedate_to_datetime(modified_since)
            lm_dt = _eu.parsedate_to_datetime(last_modified)
            if lm_dt is not None and since_dt is not None and lm_dt <= since_dt:
                return True
        except (ValueError, TypeError, OverflowError):
            pass

    return False
