"""app/core/exception_handler.py — Global exception handler registration.

Registers handlers on the FastAPI app so every BaseExceptionError subclass
produces a consistent JSON response shape:
    {"error": "<message>"}
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.base_exception import BaseExceptionError


async def base_exception_handler(request: Request, exc: BaseExceptionError) -> JSONResponse:  # noqa: ARG001
    return JSONResponse(
        content={"error": exc.message},
        status_code=exc.status_code,
    )


def register_exception_handlers(app: FastAPI) -> FastAPI:
    app.add_exception_handler(BaseExceptionError, base_exception_handler)  # type: ignore[arg-type]
    return app
