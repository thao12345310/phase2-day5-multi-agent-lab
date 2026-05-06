"""Tracing hooks — lightweight span tracking with optional external provider.

Provides:
- trace_span: context manager measuring duration per agent/operation
- TracingProvider: pluggable interface for LangSmith/Langfuse/OTel
- ConsoleTracingProvider: default provider that logs spans via Rich

Students who have LangSmith or Langfuse keys can swap in their own provider.
"""

import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Protocol


class TracingProvider(Protocol):
    """Interface for external tracing backends (LangSmith, Langfuse, OTel)."""

    def on_span_start(self, name: str, attributes: dict[str, Any]) -> None: ...
    def on_span_end(self, name: str, duration_seconds: float, attributes: dict[str, Any]) -> None: ...


class ConsoleTracingProvider:
    """Default provider — just records spans in-memory for persistence."""

    def __init__(self) -> None:
        self.spans: list[dict[str, Any]] = []

    def on_span_start(self, name: str, attributes: dict[str, Any]) -> None:
        pass  # Console logging handled by log_agent_event

    def on_span_end(self, name: str, duration_seconds: float, attributes: dict[str, Any]) -> None:
        self.spans.append({
            "name": name,
            "duration_seconds": duration_seconds,
            "timestamp": time.time(),
            "attributes": attributes,
        })


# Global provider — students can replace with LangSmith/Langfuse provider
_provider: TracingProvider = ConsoleTracingProvider()


def set_tracing_provider(provider: TracingProvider) -> None:
    """Swap in an external tracing provider (LangSmith, Langfuse, OTel)."""
    global _provider
    _provider = provider


def get_tracing_provider() -> TracingProvider:
    """Get the current tracing provider."""
    return _provider


@contextmanager
def trace_span(name: str, attributes: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
    """Measure duration of a named operation and report to the tracing provider.

    Usage:
        with trace_span("researcher", {"query": "..."}) as span:
            # do work
            span["sources_found"] = 5  # add runtime attributes

    The span dict is yielded so callers can enrich it with runtime data.
    On exit, duration is calculated and sent to the provider.
    """
    attrs = attributes or {}
    span: dict[str, Any] = {
        "name": name,
        "start_time": time.time(),
        "duration_seconds": None,
        **attrs,
    }

    _provider.on_span_start(name, attrs)
    started = time.perf_counter()

    try:
        yield span
    finally:
        span["duration_seconds"] = time.perf_counter() - started
        span["duration_ms"] = span["duration_seconds"] * 1000
        _provider.on_span_end(name, span["duration_seconds"], span)
