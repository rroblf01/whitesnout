"""Tests for ASGI lifespan, health check, and Prometheus hook."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import ASGITestClient
from whitesnout import WhiteSnout

# ---------- Lifespan ----------


async def test_lifespan_startup_complete(tmp_path: Path) -> None:
    app = WhiteSnout(directory=str(tmp_path))
    scope = {"type": "lifespan"}
    queue = [{"type": "lifespan.startup"}, {"type": "lifespan.shutdown"}]
    sent: list[dict] = []

    async def receive() -> dict:
        return queue.pop(0)

    async def send(event: dict) -> None:
        sent.append(event)

    await app(scope, receive, send)
    assert {"type": "lifespan.startup.complete"} in sent
    assert {"type": "lifespan.shutdown.complete"} in sent


async def test_lifespan_shutdown_only(tmp_path: Path) -> None:
    app = WhiteSnout(directory=str(tmp_path))
    scope = {"type": "lifespan"}
    sent: list[dict] = []

    async def receive() -> dict:
        return {"type": "lifespan.shutdown"}

    async def send(event: dict) -> None:
        sent.append(event)

    await app(scope, receive, send)
    assert sent == [{"type": "lifespan.shutdown.complete"}]


async def test_websocket_passes_through_to_inner_app(tmp_path: Path) -> None:
    received: list[dict] = []

    async def inner(scope, receive, send):
        received.append(scope)
        await send({"type": "websocket.accept"})
        await send({"type": "websocket.close", "code": 1000})

    app = WhiteSnout(inner, directory=str(tmp_path))
    scope = {"type": "websocket", "path": "/ws", "headers": []}
    sent: list[dict] = []

    async def receive() -> dict:
        return {"type": "websocket.connect"}

    async def send(event: dict) -> None:
        sent.append(event)

    await app(scope, receive, send)
    assert len(received) == 1
    assert received[0]["type"] == "websocket"
    assert sent[0]["type"] == "websocket.accept"


async def test_lifespan_inner_app_still_gets_event(tmp_path: Path) -> None:
    received: list[dict] = []

    async def inner(scope, receive, send):
        received.append(scope)

    app = WhiteSnout(inner, directory=str(tmp_path))
    scope = {"type": "lifespan"}

    async def receive() -> dict:
        return {"type": "lifespan.startup"}

    async def send(event: dict) -> None:
        pass

    await app(scope, receive, send)
    assert len(received) == 1


# ---------- Health check ----------


async def test_health_check_returns_200_ok(tmp_path: Path) -> None:
    app = WhiteSnout(directory=str(tmp_path), health_check_path="/healthz")
    client = ASGITestClient(app)
    r = await client.get("/healthz")
    assert r["status"] == 200
    assert r["body"] == b"OK"
    assert r["headers"][b"cache-control"] == b"no-store"
    assert r["headers"][b"content-type"] == b"text/plain; charset=utf-8"


async def test_health_check_bypasses_disk(tmp_path: Path) -> None:
    # No files on disk; health check still returns 200
    app = WhiteSnout(directory=str(tmp_path), health_check_path="/healthz")
    client = ASGITestClient(app)
    r = await client.get("/healthz")
    assert r["status"] == 200


async def test_health_check_not_set_returns_404(tmp_path: Path) -> None:
    app = WhiteSnout(directory=str(tmp_path))
    client = ASGITestClient(app)
    r = await client.get("/healthz")
    assert r["status"] == 404


async def test_health_check_fires_on_request_hook(tmp_path: Path) -> None:
    calls: list[dict] = []

    def hook(info: dict) -> None:
        calls.append(info)

    app = WhiteSnout(
        directory=str(tmp_path),
        health_check_path="/healthz",
        on_request=hook,
    )
    client = ASGITestClient(app)
    await client.get("/healthz")
    assert len(calls) == 1
    assert calls[0]["status"] == 200
    assert calls[0]["length"] == 2


# ---------- Prometheus hook ----------


def test_prometheus_hook_records_counts(tmp_path: Path) -> None:
    pytest.importorskip("prometheus_client")
    from prometheus_client import CollectorRegistry

    from whitesnout.prometheus import PrometheusHook

    reg = CollectorRegistry()
    hook = PrometheusHook(registry=reg)

    info = {
        "method": "GET",
        "path": "/a.css",
        "status": 200,
        "length": 100,
        "elapsed_s": 0.005,
        "scope": {},
    }
    hook(info)
    hook(info)

    # Counter sample value
    val = reg.get_sample_value(
        "whitesnout_requests_total", {"method": "GET", "status": "200"}
    )
    assert val == 2.0
    bytes_val = reg.get_sample_value(
        "whitesnout_response_bytes_total", {"method": "GET"}
    )
    assert bytes_val == 200.0


def test_prometheus_hook_histogram_records_duration(tmp_path: Path) -> None:
    pytest.importorskip("prometheus_client")
    from prometheus_client import CollectorRegistry

    from whitesnout.prometheus import PrometheusHook

    reg = CollectorRegistry()
    hook = PrometheusHook(registry=reg)
    hook(
        {
            "method": "GET",
            "path": "/x",
            "status": 304,
            "length": 0,
            "elapsed_s": 0.012,
            "scope": {},
        }
    )
    count = reg.get_sample_value(
        "whitesnout_request_duration_seconds_count",
        {"method": "GET", "status": "304"},
    )
    assert count == 1.0


async def test_prometheus_hook_works_end_to_end(tmp_path: Path) -> None:
    pytest.importorskip("prometheus_client")
    from prometheus_client import CollectorRegistry

    from whitesnout.prometheus import PrometheusHook

    (tmp_path / "a.css").write_text("body{}")
    reg = CollectorRegistry()
    hook = PrometheusHook(registry=reg)

    app = WhiteSnout(directory=str(tmp_path), on_request=hook)
    client = ASGITestClient(app)
    r = await client.get("/a.css")
    assert r["status"] == 200

    val = reg.get_sample_value(
        "whitesnout_requests_total", {"method": "GET", "status": "200"}
    )
    assert val == 1.0


def test_prometheus_hook_missing_lib_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "prometheus_client":
            raise ImportError("simulated")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    from whitesnout.prometheus import PrometheusHook

    with pytest.raises(ImportError, match="prometheus_client"):
        PrometheusHook()
