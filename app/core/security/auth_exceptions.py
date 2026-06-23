"""app/core/security/auth_exceptions.py — Auth-specific exception subclasses."""

from app.core.base_exception import BaseExceptionError


class AccessTokenExpiredError(BaseExceptionError):
    def __init__(self) -> None:
        super().__init__(message="Access token has expired", status_code=401)


class InvalidTokenError(BaseExceptionError):
    def __init__(self) -> None:
        super().__init__(message="Invalid or malformed token", status_code=401)
