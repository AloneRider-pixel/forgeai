from __future__ import annotations

from contextlib import contextmanager
from time import perf_counter

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from prometheus_client import Counter, Histogram, generate_latest

SERVICE_NAME = "forgeai"

_reviews_started = Counter("forgeai_reviews_started_total", "Review jobs started")
_reviews_completed = Counter(
    "forgeai_reviews_completed_total", "Review jobs completed", ["status"]
)
_review_duration = Histogram(
    "forgeai_review_duration_seconds", "Review job processing duration"
)


def configure_tracing() -> None:
    provider = TracerProvider(resource=Resource.create({"service.name": SERVICE_NAME}))
    trace.set_tracer_provider(provider)


def metrics_payload() -> tuple[bytes, str]:
    return generate_latest(), "text/plain; version=0.0.4; charset=utf-8"


@contextmanager
def review_span(job_id: str):
    _reviews_started.inc()
    tracer = trace.get_tracer(SERVICE_NAME)
    with tracer.start_as_current_span("forgeai.review", attributes={"job.id": job_id}):
        started = perf_counter()
        try:
            yield
        except Exception:
            _reviews_completed.labels(status="failed").inc()
            raise
        else:
            _reviews_completed.labels(status="succeeded").inc()
        finally:
            _review_duration.observe(perf_counter() - started)
