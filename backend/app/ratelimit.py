# backend/app/ratelimit.py
# Limite de requêtes par clé (adresse IP) sur une fenêtre glissante, en mémoire d'un seul processus
import threading
import time
from collections import deque
from collections.abc import Callable


class RateLimiter:
    def __init__(self, limit: int, window_seconds: float, clock: Callable[[], float] = time.monotonic):
        self.limit = limit
        self.window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def retry_after(self, key: str) -> int | None:
        now = self._clock()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= now - self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return max(1, int(hits[0] + self.window - now) + 1)
            hits.append(now)
            return None
