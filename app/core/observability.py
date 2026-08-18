"""Foundation-level observability.

- request_id per request (also echoed to the client via X-Request-ID)
- start/end/duration/status logging per request
- user_id/conversation_id attached where available

This is deliberately NOT the OwnMonitor platform — it exists so V1.1 failures
are debuggable. Never log tokens, API keys, or sensitive content.
"""

from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core import metrics as core_metrics

logger = logging.getLogger("app.request")


def request_endpoint(path: str) -> str:
    """Classify a request path into the bounded endpoint label for the HTTP
    traffic counter. Finite enum — never include ids, content, or raw paths."""
    return "chat" if path.startswith("/api/v1/chat") else "other"


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        start = time.perf_counter()
        request.state.request_id = request_id
        response = None
        try:
            response = await call_next(request)
            return response
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            path = request.url.path
            # Scrape noise must not pollute the traffic signal; everything
            # else counts once per request regardless of outcome (fail-open).
            if path != "/metrics":
                core_metrics.safe_count_http(request_endpoint(path))
            if response is not None:
                response.headers["X-Request-ID"] = request_id
            logger.info(
                "request req_id=%s method=%s path=%s status=%s duration_ms=%.1f",
                request_id,
                request.method,
                request.url.path,
                getattr(response, "status_code", "?"),
                duration_ms,
            )