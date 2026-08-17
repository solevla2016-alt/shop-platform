"""In-memory rate limiting dependency."""

from collections import defaultdict, deque
from time import monotonic

from fastapi import Request

from app.core.exceptions import TooManyRequestsError


class RateLimiter:
    """Simple IP-based in-memory rate limiter."""

    def __init__(self, max_requests: int, window_seconds: int):
        """Initialize limiter."""
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(deque)

    def get_client_ip(self, request: Request) -> str:
        """Extract client IP from request."""
        forwarded_for = request.headers.get("x-forwarded-for")

        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        if request.client and request.client.host:
            return request.client.host

        return "unknown"

    async def __call__(self, request: Request) -> None:
        """Check request rate limit."""
        client_ip = self.get_client_ip(request)
        now = monotonic()
        client_window = self.requests[client_ip]

        while client_window and now - client_window[0] >= self.window_seconds:
            client_window.popleft()

        if len(client_window) >= self.max_requests:
            raise TooManyRequestsError()

        client_window.append(now)

        if len(self.requests) > 10000:
            empty_keys = [key for key, window in self.requests.items() if not window]
            for key in empty_keys:
                del self.requests[key]
