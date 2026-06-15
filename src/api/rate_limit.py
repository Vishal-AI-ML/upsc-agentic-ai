"""Simple in-memory rate limiting middleware.

Per client-IP, allows `rate_limit_requests` within `rate_limit_period` seconds
(values from settings). Beyond that -> 429 Too Many Requests.

Note: in-memory = single process. Dev/single-instance ke liye perfect.
Multi-worker / multi-instance production mein Redis-backed limiter chahiye
(baad mein Phase 4 mein dekhenge).
"""
import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.core.config import settings

# In requests jinpe rate limit NAHI lagega (health checks, docs).
_EXEMPT_PATHS = {"/", "/health", "/docs", "/redoc", "/openapi.json"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window-ish sliding limiter using a deque of timestamps per IP."""

    def __init__(self, app, max_requests: int | None = None, period: int | None = None):
        super().__init__(app)
        self.max_requests = max_requests or settings.rate_limit_requests
        self.period = period or settings.rate_limit_period
        self._hits: dict[str, deque] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in _EXEMPT_PATHS:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window_start = now - self.period

        dq = self._hits[client_ip]
        # purane (window ke bahar) timestamps hatao
        while dq and dq[0] < window_start:
            dq.popleft()

        if len(dq) >= self.max_requests:
            retry_after = int(self.period - (now - dq[0])) + 1
            return JSONResponse(
                status_code=429,
                content={
                    "detail": (
                        f"Too many requests. Limit is {self.max_requests} "
                        f"per {self.period}s. Retry after {retry_after}s."
                    )
                },
                headers={"Retry-After": str(retry_after)},
            )

        dq.append(now)
        return await call_next(request)
