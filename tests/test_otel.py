"""Tests for whitesnout.otel.OpenTelemetryHook."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import ASGITestClient
from whitesnout import WhiteSnout


def _build_in_memory_tracer():
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("whitesnout-test")
    trace.set_tracer_provider(provider)
    return tracer, exporter


def test_otel_hook_records_span_attributes() -> None:
    pytest.importorskip("opentelemetry")
    from whitesnout.otel import OpenTelemetryHook

    tracer, exporter = _build_in_memory_tracer()
    hook = OpenTelemetryHook(tracer=tracer)

    hook(
        {
            "method": "GET",
            "path": "/a.css",
            "status": 200,
            "length": 1234,
            "elapsed_s": 0.001,
            "scope": {},
        }
    )

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    s = spans[0]
    assert s.name == "GET /a.css"
    assert s.attributes["http.request.method"] == "GET"
    assert s.attributes["http.response.status_code"] == 200
    assert s.attributes["http.response.body.size"] == 1234
    assert s.attributes["url.path"] == "/a.css"


def test_otel_hook_sets_error_status_on_5xx() -> None:
    pytest.importorskip("opentelemetry")
    from opentelemetry.trace import StatusCode

    from whitesnout.otel import OpenTelemetryHook

    tracer, exporter = _build_in_memory_tracer()
    hook = OpenTelemetryHook(tracer=tracer)
    hook(
        {
            "method": "GET",
            "path": "/x",
            "status": 503,
            "length": 0,
            "elapsed_s": 0.001,
            "scope": {},
        }
    )
    span = exporter.get_finished_spans()[0]
    assert span.status.status_code == StatusCode.ERROR


def test_otel_hook_ok_status_on_404() -> None:
    pytest.importorskip("opentelemetry")
    from opentelemetry.trace import StatusCode

    from whitesnout.otel import OpenTelemetryHook

    tracer, exporter = _build_in_memory_tracer()
    hook = OpenTelemetryHook(tracer=tracer)
    hook(
        {
            "method": "GET",
            "path": "/missing",
            "status": 404,
            "length": 0,
            "elapsed_s": 0.001,
            "scope": {},
        }
    )
    span = exporter.get_finished_spans()[0]
    # 404 is not 5xx — OK from the server's perspective
    assert span.status.status_code == StatusCode.OK


async def test_otel_hook_end_to_end(tmp_path: Path) -> None:
    pytest.importorskip("opentelemetry")
    from whitesnout.otel import OpenTelemetryHook

    (tmp_path / "a.css").write_text("body{}")
    tracer, exporter = _build_in_memory_tracer()
    hook = OpenTelemetryHook(tracer=tracer)

    app = WhiteSnout(directory=str(tmp_path), on_request=hook)
    client = ASGITestClient(app)
    r = await client.get("/a.css")
    assert r["status"] == 200

    spans = exporter.get_finished_spans()
    assert any(s.name == "GET /a.css" for s in spans)


def test_otel_hook_missing_lib_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("opentelemetry"):
            raise ImportError("simulated")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    from whitesnout.otel import OpenTelemetryHook

    with pytest.raises(ImportError, match="opentelemetry-api"):
        OpenTelemetryHook()
