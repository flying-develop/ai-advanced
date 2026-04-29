"""Sliding-window in-memory rate limiter per client IP."""

import asyncio
import time
import logging
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class RateLimiter:
    """Per-IP sliding-window rate limiter. Thread-safe via asyncio.Lock."""

    def __init__(self, rpm: int) -> None:
        self._rpm = rpm
        self._windows: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def is_allowed(self, client_ip: str) -> bool:
        """Return True if this IP is within the rate limit."""
        async with self._lock:
            now = time.monotonic()
            window = self._windows[client_ip]
            cutoff = now - 60.0
            while window and window[0] < cutoff:
                window.popleft()
            if len(window) >= self._rpm:
                return False
            window.append(now)
            return True
