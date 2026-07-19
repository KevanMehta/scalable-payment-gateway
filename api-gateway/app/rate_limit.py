import threading
import time
from collections import defaultdict, deque


class InMemoryRateLimiter:
    """Per-process sliding-window limiter for the reference API."""

    def __init__(self, requests: int, window_seconds: int):
        self.requests = requests
        self.window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, identity: str, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else now
        cutoff = current - self.window_seconds
        with self._lock:
            timestamps = self._requests[identity]
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()
            if len(timestamps) >= self.requests:
                return False
            timestamps.append(current)
            return True
