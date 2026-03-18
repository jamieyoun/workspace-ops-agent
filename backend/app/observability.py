"""Structured logging middleware: request id, route, latency."""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.metrics_store import record_request

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log each request with structured fields: request_id, route, method, latency_ms."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())[:8]
        route = f"{request.method} {request.url.path}"
        start = time.perf_counter()
        try:
            response = await call_next(request)
            latency_ms = (time.perf_counter() - start) * 1000
            record_request(route, latency_ms)
            logger.info(
                "request_id=%s route=%s method=%s status_code=%s latency_ms=%.2f",
                request_id,
                route,
                request.method,
                response.status_code,
                latency_ms,
            )
            response.headers["x-request-id"] = request_id
            return response
        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            record_request(route, latency_ms)
            logger.error(
                "request_id=%s route=%s method=%s latency_ms=%.2f error=%s",
                request_id,
                route,
                request.method,
                latency_ms,
                str(e),
            )
            raise
