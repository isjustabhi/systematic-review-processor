"""Global API rate limiter to reduce 429 errors."""

import threading
import time


class ApiRateLimiter:
    """Serialize API calls with a minimum gap between requests."""

    def __init__(self, min_interval_sec: float = 3.0):
        self._min_interval = min_interval_sec
        self._lock = threading.Lock()
        self._last_call = 0.0

    def acquire(self) -> None:
        with self._lock:
            elapsed = time.monotonic() - self._last_call
            if elapsed < self._min_interval:
                time.sleep(self._min_interval - elapsed)
            self._last_call = time.monotonic()
