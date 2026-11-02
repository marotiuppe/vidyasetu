"""Pure ASGI middleware: security headers and request ids, body size, rate limits, error boundary.

Order (outermost first) is set in main.py. These are plain ASGI classes rather than
BaseHTTPMiddleware so that request bodies can be capped while they stream.
"""

import logging
import uuid

from fastapi import HTTPException
from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import get_settings
from app.core.rate_limit import client_ip, limiter, rule_for

logger = logging.getLogger("app.errors")

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; "
    "object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
)
PERMISSIONS_POLICY = "camera=(), microphone=(), geolocation=(), payment=()"
# Swagger UI and the schema are development-only and load their assets from a CDN.
DEV_DOC_PATHS = frozenset({"/api/docs", "/api/openapi.json"})
HSTS = "max-age=31536000; includeSubDomains"


def _state(scope: Scope) -> dict[str, object]:
    state = scope.get("state")
    if not isinstance(state, dict):
        state = {}
        scope["state"] = state
    return state


class SecurityHeadersMiddleware:
    """Adds security headers and a server-generated X-Request-ID to every HTTP response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        # Client-supplied request ids are never trusted.
        request_id = uuid.uuid4().hex
        _state(scope)["request_id"] = request_id
        path = str(scope.get("path", ""))
        production = get_settings().is_production
        skip_csp = not production and path in DEV_DOC_PATHS
        is_api = path.startswith("/api/")

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = request_id
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
                headers["Permissions-Policy"] = PERMISSIONS_POLICY
                headers["Cross-Origin-Opener-Policy"] = "same-origin"
                if not skip_csp:
                    headers["Content-Security-Policy"] = CSP
                if production:
                    headers["Strict-Transport-Security"] = HSTS
                if is_api and "cache-control" not in headers:
                    headers["Cache-Control"] = "no-store"
            await send(message)

        await self.app(scope, receive, send_with_headers)


class BodySizeLimitMiddleware:
    """Rejects bodies above settings.max_body_bytes, by Content-Length or while streaming."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = get_settings().max_body_bytes
        declared = Headers(scope=scope).get("content-length")
        if declared is not None:
            try:
                too_big = int(declared) > limit
            except ValueError:
                too_big = True
            if too_big:
                response = JSONResponse(
                    {"detail": "Request body too large", "code": "payload_too_large"},
                    status_code=413,
                )
                await response(scope, receive, send)
                return

        seen = 0

        async def limited_receive() -> Message:
            nonlocal seen
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > limit:
                    # HTTPException (not a custom error) so FastAPI does not turn it into a 400.
                    raise HTTPException(413, detail="Request body too large")
            return message

        await self.app(scope, limited_receive, send)


class RateLimitMiddleware:
    """Per-IP limits on /api paths; exceeding returns 429 with Retry-After."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") == "OPTIONS":
            await self.app(scope, receive, send)
            return
        rule = rule_for(str(scope.get("path", "")))
        if rule is not None:
            bucket, limit = rule
            retry_after = limiter.hit(f"{bucket}:{client_ip(scope)}", limit)
            if retry_after is not None:
                response = JSONResponse(
                    {"detail": "Too many requests", "code": "rate_limited"},
                    status_code=429,
                    headers={"Retry-After": str(retry_after)},
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


class ErrorBoundaryMiddleware:
    """Turns unhandled exceptions into a generic 500. Logs the exception type and request id only,
    so messages (which can contain SQL parameters or personal data) never reach the logs."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def track_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, track_send)
        except Exception as exc:
            request_id = _state(scope).get("request_id")
            logger.error(
                "Unhandled %s (request_id=%s)", type(exc).__name__, request_id
            )
            if started:
                # The response is already on its way; ending here closes it without a traceback.
                return
            response = JSONResponse(
                {
                    "detail": "Internal server error",
                    "code": "internal_error",
                    "request_id": request_id,
                },
                status_code=500,
            )
            await response(scope, receive, send)
