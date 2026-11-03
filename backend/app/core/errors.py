from typing import Any


class IdentityInUse(Exception):
    """A username, email or mobile number is already used by another account (HTTP 409)."""

    def __init__(self, detail: str, code: str) -> None:
        super().__init__(detail)
        self.detail = detail
        self.code = code


class ApiError(Exception):
    """An error response with a stable machine-readable `code` (shape: detail + code).

    `detail` is text, or a list of per-row errors ({row, message}) for bulk writes.
    """

    def __init__(
        self,
        status_code: int,
        detail: str | list[dict[str, Any]],
        code: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail: str | list[dict[str, Any]] = detail
        self.code = code
        self.headers = headers

