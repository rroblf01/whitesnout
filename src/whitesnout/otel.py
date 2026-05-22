"""OpenTelemetry adapter for the ``on_request`` observability hook.

Records every served request as a span on the configured tracer. Drop-in
usage::

    from whitesnout import WhiteSnout
    from whitesnout.otel import OpenTelemetryHook

    hook = OpenTelemetryHook()
    app = WhiteSnout(directory="static", on_request=hook)

The hook adds these span attributes (OpenTelemetry semconv ``http.*``):

- ``http.request.method``
- ``http.response.status_code``
- ``http.response.body.size``
- ``url.path``

Span status is set to ``ERROR`` for any 5xx response, ``OK`` otherwise.
Span name follows the ``"{METHOD} {path}"`` convention used by the
``opentelemetry-instrumentation-*`` packages.
"""

from __future__ import annotations

from typing import Any


class OpenTelemetryHook:
    def __init__(
        self, tracer: Any = None, instrumentation_name: str = "whitesnout"
    ) -> None:
        try:
            from opentelemetry import trace
            from opentelemetry.trace import Status, StatusCode
        except ImportError as e:
            raise ImportError(
                "OpenTelemetryHook requires `opentelemetry-api`. "
                "Install with: pip install opentelemetry-api"
            ) from e

        self._tracer = tracer or trace.get_tracer(instrumentation_name)
        self._Status = Status
        self._StatusCode = StatusCode

    def __call__(self, info: dict[str, Any]) -> None:
        method = info["method"]
        path = info["path"]
        status = info["status"]

        with self._tracer.start_as_current_span(f"{method} {path}") as span:
            span.set_attribute("http.request.method", method)
            span.set_attribute("http.response.status_code", status)
            span.set_attribute("url.path", path)
            length = info.get("length", 0)
            if length:
                span.set_attribute("http.response.body.size", length)
            if status >= 500:
                span.set_status(self._Status(self._StatusCode.ERROR))
            else:
                span.set_status(self._Status(self._StatusCode.OK))
