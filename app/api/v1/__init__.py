"""app/api/v1/__init__.py — API v1 router assembly.

All domain sub-routers are registered here.
Add new routers by importing and calling api_v1_router.include_router().
"""

from fastapi import APIRouter

from app.api.v1.routers.health_routes import health_router
from app.api.v1.routers.auth_routes import auth_router

api_v1_router = APIRouter(prefix="/api/v1")

# ── Core infrastructure routes ────────────────────────────────────────────────
api_v1_router.include_router(health_router)

# ── Domain routes ─────────────────────────────────────────────────────────────
api_v1_router.include_router(auth_router)
# from app.api.v1.routers.user_routes import user_router
# api_v1_router.include_router(user_router)
#
# from app.api.v1.routers.subscription_routes import subscription_router
# api_v1_router.include_router(subscription_router)
#
# from app.api.v1.routers.transaction_routes import transaction_router
# api_v1_router.include_router(transaction_router)
#
# from app.api.v1.routers.upload_routes import upload_router
# api_v1_router.include_router(upload_router)
#
# from app.api.v1.routers.webhook_routes import webhook_router
# api_v1_router.include_router(webhook_router)
#
# Admin sub-group:
# from app.api.v1.routers.admin import admin_router
# api_v1_router.include_router(admin_router)
