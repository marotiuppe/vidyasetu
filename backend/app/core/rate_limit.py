"""In-memory sliding-window rate limiter keyed by client IP (one process; fine for one instance)."""

import math
import threading
import time
from collections import deque

from starlette.types import Scope

from app.core.config import get_settings

WINDOW_SECONDS = 60.0
_SWEEP_EVERY_SECONDS = 60.0
_MAX_KEYS = 50_000


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        self._last_sweep = time.monotonic()

    def hit(self, key: str, limit: int) -> int | None:
        """Record a request. Returns None when allowed, or the Retry-After seconds when not."""
        now = time.monotonic()
        with self._lock:
            if now - self._last_sweep >= _SWEEP_EVERY_SECONDS or len(self._hits) > _MAX_KEYS:
                self._sweep(now)
            window = self._hits.setdefault(key, deque())
            cutoff = now - WINDOW_SECONDS
            while window and window[0] <= cutoff:
                window.popleft()
            if len(window) >= limit:
                return max(1, math.ceil(window[0] + WINDOW_SECONDS - now))
            window.append(now)
            return None

    def _sweep(self, now: float) -> None:
        cutoff = now - WINDOW_SECONDS
        for key in [k for k, q in self._hits.items() if not q or q[-1] <= cutoff]:
            del self._hits[key]
        self._last_sweep = now


limiter = SlidingWindowLimiter()


def client_ip(scope: Scope) -> str:
    """The client address. Behind a proxy, the last X-Forwarded-For entry when trusted.

    The last entry is the one our own proxy appended; earlier ones can be forged by the client."""
    if get_settings().trust_proxy_headers:
        for name, value in scope.get("headers", []):
            if name == b"x-forwarded-for":
                last: str = value.decode("latin-1").split(",")[-1].strip()
                if last:
                    return last
    client = scope.get("client")
    return str(client[0]) if client else "unknown"


def rule_for(path: str) -> tuple[str, int] | None:
    """(bucket, requests per minute) for an API path; None for paths that are not limited."""
    if not path.startswith("/api/"):
        return None
    settings = get_settings()
    if path in ("/api/v1/auth/login", "/api/v1/auth/login/mfa"):
        return "login", settings.rate_limit_login_per_minute
    if path.startswith("/api/v1/auth/mfa/"):
        return "mfa", settings.rate_limit_mfa_per_minute
    if path == "/api/v1/me/export" or (
        path.startswith("/api/v1/students/") and path.endswith("/export") and path.count("/") == 5
    ):
        return "export", settings.rate_limit_export_per_minute
    if path == "/api/v1/auth/refresh":
        return "refresh", settings.rate_limit_refresh_per_minute
    if path == "/api/v1/auth/change-password":
        return "change-password", settings.rate_limit_change_password_per_minute
    return "api", settings.rate_limit_api_per_minute
