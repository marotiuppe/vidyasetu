"""Per-request facts (client IP, request id) for code that has no Request in hand, e.g. audit."""

from contextvars import ContextVar

request_ip: ContextVar[str | None] = ContextVar("request_ip", default=None)
request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
