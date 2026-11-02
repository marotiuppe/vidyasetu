class IdentityInUse(Exception):
    """A username, email or mobile number is already used by another account (HTTP 409)."""

    def __init__(self, detail: str, code: str) -> None:
        super().__init__(detail)
        self.detail = detail
        self.code = code
