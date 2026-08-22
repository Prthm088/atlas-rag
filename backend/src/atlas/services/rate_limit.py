import asyncio
import time
from collections import defaultdict, deque

from atlas.errors import AppError


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def enforce(self, key: str, *, limit: int, window_seconds: int) -> None:
        now = time.monotonic()
        cutoff = now - window_seconds
        async with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                retry_after = max(1, int(events[0] + window_seconds - now))
                raise AppError(
                    "rate_limit_exceeded",
                    "You have reached the temporary request limit. Please try again shortly.",
                    status_code=429,
                    details={"retry_after_seconds": retry_after},
                )
            events.append(now)


rate_limiter = InMemoryRateLimiter()
