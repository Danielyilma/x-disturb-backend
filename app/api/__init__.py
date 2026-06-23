"""app/api/__init__.py — Application factory.

Bootstrap order:
  1. Create FastAPI instance
  2. Register security headers middleware
  3. Register CORS middleware (explicit origin allow-list)
  4. Mount all domain routers via register_router()
  5. Register global exception handlers

Security headers applied on every response:
  - X-Content-Type-Options: nosniff
  - X-Frame-Options: DENY
  - Permissions-Policy: camera=(), microphone=(), geolocation=()
  - Referrer-Policy: strict-origin-when-cross-origin
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.api.v1 import api_v1_router
from app.config import MySettings
from app.core.exception_handler import register_exception_handlers


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds secure HTTP response headers to every response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


def register_router(app: FastAPI) -> None:
    app.include_router(api_v1_router)


def create_app() -> FastAPI:
    app = FastAPI(
        title="x-disturb API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Security headers on every response
    app.add_middleware(SecurityHeadersMiddleware)

    # CORS — strict allow-list; never wildcard (*) in production
    app.add_middleware(
        CORSMiddleware,
        allow_origins=MySettings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # Domain routers
    register_router(app)

    # Global exception handling
    register_exception_handlers(app)

    return app
