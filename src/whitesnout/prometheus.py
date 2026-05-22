"""Prometheus adapter for the ``on_request`` observability hook.

Drop-in usage::

    from prometheus_client import CollectorRegistry, make_asgi_app
    from whitesnout import WhiteSnout
    from whitesnout.prometheus import PrometheusHook

    metrics = PrometheusHook()
    app = WhiteSnout(directory="static", on_request=metrics)

The hook records:

- ``whitesnout_requests_total{method,status}`` — counter
- ``whitesnout_response_bytes_total{method}`` — counter
- ``whitesnout_request_duration_seconds{method,status}`` — histogram

It uses ``prometheus_client``'s default registry. Pass an explicit
``registry`` to keep metrics isolated (e.g. for tests or multi-app setups).
"""

from __future__ import annotations

from typing import Any


class PrometheusHook:
    def __init__(self, registry: Any = None, namespace: str = "whitesnout") -> None:
        try:
            from prometheus_client import (
                Counter,
                Histogram,
            )
        except ImportError as e:
            raise ImportError(
                "PrometheusHook requires `prometheus_client`. "
                "Install with: pip install prometheus-client"
            ) from e

        kwargs: dict = {"registry": registry} if registry is not None else {}

        self.requests = Counter(
            f"{namespace}_requests_total",
            "Total HTTP requests served by WhiteSnout",
            labelnames=("method", "status"),
            **kwargs,
        )
        self.response_bytes = Counter(
            f"{namespace}_response_bytes_total",
            "Total bytes sent in response bodies",
            labelnames=("method",),
            **kwargs,
        )
        self.duration = Histogram(
            f"{namespace}_request_duration_seconds",
            "Request handling time in seconds",
            labelnames=("method", "status"),
            buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
            **kwargs,
        )

    def __call__(self, info: dict[str, Any]) -> None:
        method = info["method"]
        status = str(info["status"])
        self.requests.labels(method=method, status=status).inc()
        length = info.get("length", 0)
        if length:
            self.response_bytes.labels(method=method).inc(length)
        elapsed = info.get("elapsed_s", 0.0)
        self.duration.labels(method=method, status=status).observe(elapsed)
