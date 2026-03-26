from __future__ import annotations

import time

from cachetools import TTLCache

from app.core.config import settings


class RateLimitService:
    def __init__(
        self,
        *,
        requests: int | None = None,
        window_seconds: int | None = None,
        max_users: int = 50_000,
    ) -> None:
        self._requests = requests or settings.rate_limit_requests
        self._window_seconds = window_seconds or settings.rate_limit_window_seconds
        self._hits: TTLCache[int, tuple[int, float]] = TTLCache(maxsize=max_users, ttl=self._window_seconds)

    def check(self, telegram_id: int) -> None:
        now = time.monotonic()
        count, reset_at = self._hits.get(telegram_id, (0, now + self._window_seconds))
        if now >= reset_at:
            count, reset_at = 0, now + self._window_seconds
        count += 1
        self._hits[telegram_id] = (count, reset_at)
        if count > self._requests:
            raise RateLimitExceededError(retry_after_seconds=max(1, int(reset_at - now)))


class RateLimitExceededError(Exception):
    def __init__(self, *, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"Rate limit exceeded. Retry after {retry_after_seconds}s")

