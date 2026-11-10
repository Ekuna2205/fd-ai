import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import Request

from app.core.config import get_settings
from app.core.errors import AppError


class SlidingWindowLimiter:
    """In-memory limiter: fine for one process. Use a shared store (e.g. Redis) when scaling out."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, limit: int, window: float = 60.0) -> float | None:
        """Returns seconds to wait if the limit is exceeded, else None."""
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= limit:
                return window - (now - q[0])
            q.append(now)
            return None

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = SlidingWindowLimiter()


def auth_rate_limit(request: Request) -> None:
    limit = get_settings().rate_limit_auth_per_minute
    if limit <= 0:
        return
    host = request.client.host if request.client else "unknown"
    wait = limiter.check(f"{host}:{request.url.path}", limit)
    if wait is not None:
        retry = str(max(1, int(wait) + 1))
        raise AppError("Too many attempts. Try again shortly.", 429, headers={"Retry-After": retry})


def user_rate_limit(setting_name: str):
    """Dependency factory: limits per signed-in user using the named per-minute setting (0 disables)."""
    from typing import Annotated

    from fastapi import Depends

    from app.api.deps import CurrentUser

    def dependency(user: CurrentUser) -> None:
        limit = getattr(get_settings(), setting_name)
        if limit <= 0:
            return
        wait = limiter.check(f"{setting_name}:{user.id}", limit)
        if wait is not None:
            raise AppError("Too many requests. Slow down and try again shortly.", 429,
                           headers={"Retry-After": str(max(1, int(wait) + 1))})

    return dependency
