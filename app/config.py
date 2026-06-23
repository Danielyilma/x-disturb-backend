"""app/config.py — Hierarchical settings using Pydantic BaseModel.

Pattern:
  - All values come from os.environ — never hardcoded literals.
  - A single `MySettings` singleton is imported everywhere.
  - Secrets (JWT, Firebase, Stripe) MUST be set via env vars in production.
    If missing, the app raises at startup rather than running with unsafe defaults.

Usage:
    from app.config import MySettings
    print(MySettings.FIREBASE_PROJECT_ID)
"""

import os
from enum import Enum

from dotenv import load_dotenv
from pydantic import BaseModel

# Load .env before any os.environ.get() calls.
# In Docker this is a no-op (env comes from env_file / environment block),
# but in bare local dev it ensures the file is read first.
load_dotenv(override=False)  # override=False: real env vars take precedence


class EnvironmentOptions(Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class EnvironmentSettings(BaseModel):
    ENVIRONMENT: str = os.environ.get("ENVIRONMENT", "development")

    def get_environment(self) -> "BaseConfig":
        env = self.ENVIRONMENT.lower()
        if env == EnvironmentOptions.PRODUCTION.value:
            return ProdConfig()
        if env == EnvironmentOptions.STAGING.value:
            return StagingConfig()
        return DevConfig()


class FirebaseSettings(BaseModel):
    # Option A: path to a local service account JSON file
    FIREBASE_SERVICE_ACCOUNT_KEY_PATH: str | None = os.environ.get(
        "FIREBASE_SERVICE_ACCOUNT_KEY_PATH"
    )
    # Option B: inline JSON string (preferred for Cloud Run / Secret Manager)
    FIREBASE_SERVICE_ACCOUNT_JSON: str | None = os.environ.get(
        "FIREBASE_SERVICE_ACCOUNT_JSON"
    )
    FIREBASE_STORAGE_BUCKET: str = os.environ.get("FIREBASE_STORAGE_BUCKET", "")
    FIREBASE_PROJECT_ID: str = os.environ.get("FIREBASE_PROJECT_ID", "")


class JWTSettings(BaseModel):
    JWT_ALGORITHM: str = os.environ.get("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", 30)
    )
    REFRESH_TOKEN_EXPIRE_MINUTES: int = int(
        os.environ.get("REFRESH_TOKEN_EXPIRE_MINUTES", 1440)
    )


class AfroMessageSettings(BaseModel):
    AFROMESSAGE_API_KEY: str | None = os.environ.get("AFROMESSAGE_API_KEY")
    AFROMESSAGE_IDENTIFIER: str | None = os.environ.get("AFROMESSAGE_IDENTIFIER")
    AFROMESSAGE_SENDER_NAME: str = os.environ.get("AFROMESSAGE_SENDER_NAME", "AfroMessage")


class BaseConfig(EnvironmentSettings, FirebaseSettings, JWTSettings, AfroMessageSettings):
    # TODO(security): JWT_SECRET must be provided via env — no hardcoded fallback.
    # In dev/test, an ephemeral key is generated in core/security/jwt.py with a warning.
    JWT_SECRET: str | None = os.environ.get("JWT_SECRET")

    # CORS — comma-separated list of allowed origins; never wildcard in production
    ALLOWED_ORIGINS: list[str] = [
        o.strip()
        for o in os.environ.get(
            "ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173"
        ).split(",")
        if o.strip()
    ]

    # Stripe
    STRIPE_SECRET_KEY: str | None = os.environ.get("STRIPE_SECRET_KEY")
    STRIPE_WEBHOOK_SECRET: str | None = os.environ.get("STRIPE_WEBHOOK_SECRET")

    # Chapa Payment Gateway
    CHAPA_SECRET_KEY: str | None = os.environ.get("CHAPA_SECRET_KEY")
    CHAPA_BASE_URL: str = os.environ.get("CHAPA_BASE_URL", "https://api.chapa.co/v1")
    CHAPA_RETURN_URL: str = os.environ.get("CHAPA_RETURN_URL", "http://localhost:3000/payment/success")
    CHAPA_WEBHOOK_SECRET: str | None = os.environ.get("CHAPA_WEBHOOK_SECRET")
    # Firestore collection name for subscription plans
    CHAPA_PLANS_COLLECTION: str = os.environ.get("CHAPA_PLANS_COLLECTION", "subscription_plans")

    # Google AI
    GOOGLE_API_KEY: str | None = os.environ.get("GOOGLE_API_KEY")
    GEMINI_MODEL_NAME: str = os.environ.get("GEMINI_MODEL_NAME", "gemini-2.0-flash")

    PORT: int = int(os.environ.get("PORT", 8000))


class DevConfig(BaseConfig):
    ENVIRONMENT: str = "development"


class StagingConfig(BaseConfig):
    ENVIRONMENT: str = "staging"


class ProdConfig(BaseConfig):
    ENVIRONMENT: str = "production"


# ── Singleton ────────────────────────────────────────────────────────────────
# Import this object everywhere — never instantiate a new config.
MySettings: BaseConfig = BaseConfig().get_environment()
