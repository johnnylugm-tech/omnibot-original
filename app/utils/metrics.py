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
    "omnibot_llm_tokens_total", "Total tokens used by LLM", ["model", "token_type"]
)

FCR_TOTAL = Counter(
    "omnibot_fcr_total", "Total First Contact Resolution count", ["platform", "tier", "channel"]
)

KNOWLEDGE_HIT_TOTAL = Counter(
    "omnibot_knowledge_hit_total", "Total knowledge base hits", ["source", "category"]
)

PII_MASKED_TOTAL = Counter(
    "omnibot_pii_masked_total", "Total PII masking actions", ["pii_type", "action"]
)

EMOTION_ESCALATION_TOTAL = Counter(
    "omnibot_emotion_escalation_total", "Total escalations triggered by emotion", ["emotion_type"]
)


def start_metrics_server(port: int = 8000) -> None:
    """Start Prometheus metrics server"""
    start_http_server(port)
    print(f"Metrics server started on port {port}")
