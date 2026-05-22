"""Concurrency stress tests for the caches and hot path.

Spawn a high number of concurrent requests and verify:

- All responses succeed with the expected status / body.
- The LRU + StatCache (Rust or Python fallback) survives concurrent writes
  without corruption — no AttributeError, no missing keys, no wrong sizes.
- Compressed cache (autocompress) returns identical bytes per cache key.

These are not benchmarks. They are correctness checks under load.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from tests.conftest import ASGITestClient
from whitesnout import WhiteSnout

CONCURRENCY = 200


async def test_concurrent_same_file(tmp_path: Path) -> None:
    payload = b"x" * 1024
    (tmp_path / "hot.css").write_bytes(payload)
    app = WhiteSnout(directory=str(tmp_path))
    client = ASGITestClient(app)

    async def one() -> dict:
        return await client.get("/hot.css")

    results = await asyncio.gather(*(one() for _ in range(CONCURRENCY)))

    assert all(r["status"] == 200 for r in results)
    assert all(r["body"] == payload for r in results)


async def test_concurrent_distinct_files(tmp_path: Path) -> None:
    n = 64
    for i in range(n):
        (tmp_path / f"f{i}.css").write_bytes(f"body{i}".encode())
    app = WhiteSnout(directory=str(tmp_path), max_cache_size=8)
    client = ASGITestClient(app)

    async def one(i: int) -> dict:
        return await client.get(f"/f{i % n}.css")

    results = await asyncio.gather(*(one(i) for i in range(CONCURRENCY)))
    assert all(r["status"] == 200 for r in results)
    # Body must match the URL — wrong-file leak across requests would fail this
    for r, idx in zip(results, [i % n for i in range(CONCURRENCY)], strict=True):
        assert r["body"] == f"body{idx}".encode()


async def test_concurrent_autocompress(tmp_path: Path) -> None:
    payload = b"compressible-payload-" * 200
    (tmp_path / "a.css").write_bytes(payload)
    app = WhiteSnout(directory=str(tmp_path), autocompress=True)
    client = ASGITestClient(app)

    async def one() -> dict:
        return await client.get("/a.css", headers=[(b"accept-encoding", b"gzip, br")])

    results = await asyncio.gather(*(one() for _ in range(CONCURRENCY)))
    assert all(r["status"] == 200 for r in results)
    # Every response should have the same compressed payload (cache is keyed
    # by path+mtime+encoding — concurrent races must not produce inconsistent
    # bodies for the same key).
    bodies = {r["body"] for r in results}
    # At most two distinct bodies if some hit gzip and others brotli race-wise;
    # the cache picks a single encoding per request based on Accept-Encoding,
    # which is identical here. So expect exactly one.
    assert len(bodies) == 1


async def test_concurrent_mixed_hit_miss(tmp_path: Path) -> None:
    """Half of the requests hit existing files; half hit 404s."""
    (tmp_path / "real.css").write_text("body{}")
    app = WhiteSnout(directory=str(tmp_path))
    client = ASGITestClient(app)

    async def one(i: int) -> dict:
        return await client.get("/real.css" if i % 2 == 0 else "/missing.css")

    results = await asyncio.gather(*(one(i) for i in range(CONCURRENCY)))
    statuses = [r["status"] for r in results]
    assert statuses.count(200) == CONCURRENCY // 2
    assert statuses.count(404) == CONCURRENCY // 2


async def test_concurrent_conditional_get(tmp_path: Path) -> None:
    (tmp_path / "etag.css").write_text("body{}")
    app = WhiteSnout(directory=str(tmp_path))
    client = ASGITestClient(app)

    first = await client.get("/etag.css")
    etag = first["headers"][b"etag"]

    async def one() -> dict:
        return await client.get("/etag.css", headers=[(b"if-none-match", etag)])

    results = await asyncio.gather(*(one() for _ in range(CONCURRENCY)))
    assert all(r["status"] == 304 for r in results)
    assert all(r["body"] == b"" for r in results)
