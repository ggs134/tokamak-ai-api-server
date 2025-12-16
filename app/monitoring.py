"""
Prometheus metrics for monitoring
"""

from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response
import time

# Request metrics
request_count = Counter(
    'ollama_api_requests_total',
    'Total API requests',
    ['endpoint', 'method', 'status']
)

request_duration = Histogram(
    'ollama_api_request_duration_seconds',
    'Request duration in seconds',
    ['endpoint', 'method']
)

# Token metrics
tokens_processed = Counter(
    'ollama_api_tokens_total',
    'Total tokens processed',
    ['username', 'model']
)

# Backend metrics
backend_requests = Counter(
    'ollama_backend_requests_total',
    'Backend server requests',
    ['server', 'status']
)

backend_response_time = Histogram(
    'ollama_backend_response_seconds',
    'Backend response time',
    ['server']
)

# Active connections
active_requests = Gauge(
    'ollama_api_active_requests',
    'Number of active requests'
)

# Rate limit metrics
rate_limit_hits = Counter(
    'ollama_api_rate_limit_hits_total',
    'Number of rate limit hits',
    ['username']
)

def metrics_endpoint():
    """Return Prometheus metrics"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

class RequestMetrics:
    """Context manager for request metrics"""
    
    def __init__(self, endpoint: str, method: str):
        self.endpoint = endpoint
        self.method = method
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        active_requests.inc()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        request_duration.labels(
            endpoint=self.endpoint,
            method=self.method
        ).observe(duration)
        
        status = 'error' if exc_type else 'success'
        request_count.labels(
            endpoint=self.endpoint,
            method=self.method,
            status=status
        ).inc()
        
        active_requests.dec()
