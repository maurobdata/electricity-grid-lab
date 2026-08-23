"""OpenTelemetry, off by default.

Three places are worth a span, and they are the three questions asked when something looks
wrong: *did we call Electricity Maps, and what did it say?*, *which tools did the agent
run?*, and *how long did a turn take?*

Off unless ``GRIDLAB_TRACING_ENABLED=true``, and the collector is behind a Compose profile,
so the ordinary ``make up`` stays at three containers. Instrumentation that costs a service
to run gets turned on when you want it, not always.

When disabled, :func:`span` is a no-op context manager — the call sites stay identical
either way, so there is no branch anywhere else in the codebase.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager, suppress
from typing import Any

import structlog

log = structlog.get_logger(__name__)

_tracer: Any = None
_enabled = False


def configure(*, enabled: bool, endpoint: str, service: str) -> None:
    """Set up tracing. Safe to call when the packages are absent or the collector is down.

    A missing collector must never take the lab with it. Tracing is a diagnostic, and a
    diagnostic that can break the thing it observes is worse than none.
    """
    global _tracer, _enabled

    if not enabled:
        log.debug("telemetry.disabled")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        log.warning("telemetry.unavailable", hint="pip install '.[tracing]'")
        return

    try:
        provider = TracerProvider(resource=Resource.create({"service.name": service}))
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True))
        )
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer(service)
        _enabled = True
        log.info("telemetry.enabled", endpoint=endpoint, service=service)
    except Exception as exc:
        log.warning("telemetry.setup_failed", error=str(exc))


def enabled() -> bool:
    return _enabled


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[Any]:
    """A span, or nothing at all.

    Attributes are set individually rather than in bulk so that one unserialisable value
    cannot lose the whole span.
    """
    if not _enabled or _tracer is None:
        yield None
        return

    with _tracer.start_as_current_span(name) as current:
        record(current, **attributes)
        yield current


def record(current: Any, **attributes: Any) -> None:
    """Add attributes to a span, ignoring any that cannot be set.

    Each is set individually and failures are swallowed: one unserialisable value should
    cost that attribute, not the span, and certainly not the request being traced.
    """
    if current is None:
        return
    for key, value in attributes.items():
        if value is None:
            continue
        with suppress(Exception):
            current.set_attribute(
                key, value if isinstance(value, str | int | float | bool) else str(value)
            )
