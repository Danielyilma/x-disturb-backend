"""app/api/v1/routers/health_routes.py — Health probe endpoints.

GET /api/v1/health      — public liveness probe (no auth)
GET /api/v1/health/me   — protected; returns the authenticated user's Firebase UID
"""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.dependency import CurrentUserDep

health_router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    status: str


class MeResponse(BaseModel):
    uid: str
    email: str | None = None
    email_verified: bool = False


@health_router.get("", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Public liveness probe — no authentication required."""
    return HealthResponse(status="ok")


@health_router.get("/me", response_model=MeResponse)
async def get_me(user: CurrentUserDep) -> MeResponse:
    """Protected endpoint — requires a valid Firebase ID token.

    Returns the authenticated user's Firebase UID, email, and verification status.
    Use this as a reference for wiring auth into any other route.
    """
    return MeResponse(
        uid=user["uid"],
        email=user.get("email"),
        email_verified=user.get("email_verified", False),
    )
