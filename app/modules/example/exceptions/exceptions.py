"""app/modules/example/exceptions/exceptions.py — Domain-specific exceptions.

All exceptions inherit from BaseExceptionError so they are automatically
caught by the global handler and returned as {"error": "..."} JSON responses.
"""

from app.core.base_exception import BaseExceptionError


class ExampleNotFoundError(BaseExceptionError):
    def __init__(self) -> None:
        super().__init__(message="Example not found", status_code=404)


class ExampleAlreadyExistsError(BaseExceptionError):
    def __init__(self) -> None:
        super().__init__(message="Example already exists", status_code=409)
