"""Prometheus Metrics - Phase 3"""
from prometheus_client import Counter, Histogram, Summary, start_http_server
import time

# Metrics definitions
REQUEST_COUNT = Counter(
    "omnibot_requests_total", "Total request count", [
        "method", "endpoint", "platform"]
)

REQUEST_LATENCY = Histogram(
    "omnibot_request_latency_seconds", "Request latency", ["endpoint"]
)

MESSAGE_SENTIMENT = Summary(
    "omnibot_message_sentiment", "Message sentiment intensity", ["platform"]
)

LLM_TOKEN_USAGE = Counter(
    "omnibot_llm_tokens_total", "Total tokens used by LLM", ["model"]
)


def start_metrics_server(port: int = 8000) -> None:
    """Start Prometheus metrics server"""
    start_http_server(port)
    print(f"Metrics server started on port {port}")
