"""
Request logging middleware.
Logs method, path, status code, and response time for every HTTP request.
"""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("fieldops.http")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that logs all incoming HTTP requests."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = str(uuid.uuid4())[:8]
        start_time = time.perf_counter()

        response = await call_next(request)

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        logger.info(
            "[%s] %s %s -> %d  (%.2fms)",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )

        # Attach request-id header to response for tracing
        response.headers["X-Request-ID"] = request_id
        return response
