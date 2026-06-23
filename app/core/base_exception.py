"""app/core/base_exception.py — Single base class for all domain exceptions.

Every module defines its own exception subclasses that inherit from this.
The global exception handler (exception_handler.py) catches this base class
and returns a uniform JSON error response automatically.
"""


class BaseExceptionError(Exception):
    def __init__(self, *, message: str, status_code: int) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)
