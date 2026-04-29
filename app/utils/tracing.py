"""OpenTelemetry Tracing - Phase 3"""
import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource


def setup_tracing(service_name: str = "omnibot") -> None:
    """Initialize OpenTelemetry tracer with OTLP exporter"""
    # Environment variables
    otlp_endpoint = os.getenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")

    resource = Resource(attributes={
        "service.name": service_name,
        "environment": os.getenv("ENV", "development")
    })

    provider = TracerProvider(resource=resource)

    # Use GRPC exporter for otel-collector
    try:
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)
        print(f"Tracing initialized for {service_name} -> {otlp_endpoint}")
    except Exception as e:
        print(f"Failed to initialize tracing: {e}")


# Global tracer
tracer = trace.get_tracer("omnibot")
