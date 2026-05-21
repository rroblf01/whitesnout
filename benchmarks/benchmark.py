#!/usr/bin/env python3
"""Benchmark whitesnout vs whitenoise for static file serving."""

import asyncio
import os
import platform
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path

import psutil


def generate_static_dir(target: Path) -> None:
    """Generate a realistic static file directory."""
    dir_specs: list[tuple[str, int, str]] = [
        ("css", 5, "css"),
        ("js", 8, "js"),
        ("img", 12, "png"),
        ("fonts", 4, "woff2"),
    ]
    for name, count, ext in dir_specs:
        sub = target / name
        sub.mkdir(parents=True, exist_ok=True)
        sizes = {"css": 1024, "js": 512, "img": 20480, "fonts": 4096}
        for i in range(count):
            path = sub / f"{name}_{i}.{ext}"
            path.write_bytes(os.urandom(sizes[name]))

    (target / "index.html").write_text(
        "<!DOCTYPE html>\n<html><head><title>Benchmark</title></head><body>\n"
        '<h1>Hello</h1>\n<script src="/js/js_0.js"></script>\n</body></html>'
    )


def write_whitesnout_script(static_dir: str, port: int) -> str:
    code = textwrap.dedent(f'''\
        import uvicorn
        from whitesnout import WhiteSnout

        async def api(scope, receive, send):
            if scope["type"] == "http" and scope["path"] == "/api/hello":
                body = b'{{"message":"hello"}}'
                await send({{
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [(b"content-type", b"application/json")],
                }})
                await send({{"type": "http.response.body", "body": body}})

        asgi = WhiteSnout(api, directory="{static_dir}")
        uvicorn.run(asgi, host="127.0.0.1", port={port}, log_level="error")
    ''')
    path = Path(tempfile.mkdtemp()) / "server_ws.py"
    path.write_text(code)
    return str(path)


def write_whitenoise_script(static_dir: str, port: int) -> str:
    code = textwrap.dedent(f'''\
        import json
        import uvicorn
        from a2wsgi import WSGIMiddleware
        from whitenoise import WhiteNoise

        def api(environ, start_response):
            if environ["PATH_INFO"] == "/api/hello":
                body = json.dumps({{"message": "hello"}}).encode()
                start_response("200 OK", [("content-type", "application/json")])
                return [body]
            start_response("404 Not Found", [("content-type", "text/plain")])
            return [b"Not Found"]

        wsgi_app = WhiteNoise(api, root="{static_dir}", index_file=True)
        asgi = WSGIMiddleware(wsgi_app)
        uvicorn.run(asgi, host="127.0.0.1", port={port}, log_level="error")
    ''')
    path = Path(tempfile.mkdtemp()) / "server_wn.py"
    path.write_text(code)
    return str(path)


async def benchmark_server(port: int, num_requests: int, concurrency: int) -> dict:
    import httpx

    async def worker(
        client: httpx.AsyncClient,
        urls: list[str],
        results: list[float],
    ) -> None:
        for url in urls:
            t0 = time.perf_counter()
            r = await client.get(url)
            r.raise_for_status()
            results.append(time.perf_counter() - t0)

    urls = [
        f"http://127.0.0.1:{port}/css/css_0.css",
        f"http://127.0.0.1:{port}/api/hello",
    ]
    for name in ("css", "js", "img"):
        for i in range(3):
            ext = {"css": "css", "js": "js", "img": "png"}[name]
            urls.append(f"http://127.0.0.1:{port}/{name}/{name}_{i}.{ext}")

    all_urls = (urls * (num_requests // len(urls) + 1))[:num_requests]

    # Warm-up
    async with httpx.AsyncClient() as client:
        for url in all_urls[:20]:
            await client.get(url)

    # Measure
    results: list[float] = []
    chunk_size = max(1, len(all_urls) // concurrency)
    chunks = [all_urls[i : i + chunk_size] for i in range(0, len(all_urls), chunk_size)]

    t0 = time.perf_counter()
    async with httpx.AsyncClient() as client:
        tasks = [worker(client, chunk, results) for chunk in chunks]
        await asyncio.gather(*tasks)
    elapsed = time.perf_counter() - t0

    results.sort()
    n = len(results)
    p50 = results[n // 2] if n else 0
    p99 = results[int(n * 0.99)] if n else 0

    return {
        "total_requests": num_requests,
        "concurrency": concurrency,
        "elapsed_s": round(elapsed, 2),
        "rps": round(num_requests / elapsed, 1),
        "p50_ms": round(p50 * 1000, 1),
        "p99_ms": round(p99 * 1000, 1),
    }


def measure_ram(pid: int) -> float:
    try:
        proc = psutil.Process(pid)
        time.sleep(0.5)
        return proc.memory_info().rss / 1024 / 1024
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return 0.0


async def run_server(script: str, port: int) -> tuple[subprocess.Popen, dict]:
    import httpx

    proc = subprocess.Popen(
        [sys.executable, script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )

    # Wait for server ready
    for _ in range(50):
        try:
            async with httpx.AsyncClient() as c:
                r = await c.get(f"http://127.0.0.1:{port}/api/hello", timeout=1)
                if r.status_code == 200:
                    break
        except (httpx.ConnectError, httpx.TimeoutException):
            pass
        await asyncio.sleep(0.1)
    else:
        proc.kill()
        proc.wait()
        raise RuntimeError(f"Server on port {port} did not start")

    ram = measure_ram(proc.pid)
    bench = await benchmark_server(port, num_requests=500, concurrency=10)
    bench["ram_mb"] = round(ram, 1)

    os.kill(proc.pid, signal.SIGINT)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()

    Path(script).unlink(missing_ok=True)
    return proc, bench


async def main() -> None:
    print("=== whitesnout vs whitenoise benchmark ===\n")
    print(f"Platform: {platform.system()} {platform.machine()}")
    print(f"Python: {platform.python_version()}")

    with tempfile.TemporaryDirectory() as tmp:
        static_dir = Path(tmp) / "static"
        static_dir.mkdir()
        generate_static_dir(static_dir)
        total_size = sum(f.stat().st_size for f in static_dir.rglob("*") if f.is_file())
        file_count = len(list(static_dir.rglob("*")))
        print(f"Static files: {total_size / 1024:.0f} KB across {file_count} items\n")

        ws_script = write_whitesnout_script(str(static_dir), 18921)
        _, ws_result = await run_server(ws_script, 18921)

        wn_script = write_whitenoise_script(str(static_dir), 18922)
        _, wn_result = await run_server(wn_script, 18922)

    print("\n## Resultados\n")
    print("| Servidor | RPS | P50 (ms) | P99 (ms) | RAM (MB) |")
    print("|---|---|---|---|---|")
    for label, r in [("whitesnout", ws_result), ("whitenoise", wn_result)]:
        line = (
            f"| {label} | {r['rps']:.0f} | {r['p50_ms']:.1f} | "
            f"{r['p99_ms']:.1f} | {r['ram_mb']:.1f} |"
        )
        print(line)

    a, b = ws_result, wn_result
    if a["rps"]:
        diffs = {
            "rps": ((b["rps"] - a["rps"]) / a["rps"]) * 100,
            "ram": ((b["ram_mb"] - a["ram_mb"]) / a["ram_mb"]) * 100,
        }
        parts = []
        for k, label in [("rps", "RPS"), ("ram", "RAM")]:
            d = diffs[k]
            direction = "más" if d > 0 else "menos"
            parts.append(f"{abs(d):.0f}% {direction} {label}")
        print(f"\nWhitenoise vs whitesnout: {', '.join(parts)}")


if __name__ == "__main__":
    asyncio.run(main())
