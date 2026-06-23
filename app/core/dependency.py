"""app/core/dependency.py — Central dependency injection hub.

All FastAPI Depends() factories for repositories, services, and guards
are defined here. Routes import from this file — never instantiate
dependencies inline.

Pattern:
  1. Firestore client → Repository
  2. Repository → Service (when a service also needs an external client)
  3. Auth guard — verifies Firebase ID token, returns decoded payload
  4. Role guard — checks custom claims (e.g., admin)
  5. Business guard — e.g., subscription usage limit
"""

import logging
from typing import Annotated, Any

from firebase_admin import auth as firebase_auth
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.cloud.firestore_v1.async_client import AsyncClient

from app.core.firebase import get_firestore_client, verify_firebase_token
from app.core.sms import AfroMessageClient
from app.core.chapa import ChapaClient
from app.config import MySettings
from app.modules.auth.repositories.otp_repository import OtpRepositoryImp
from app.modules.payment.repositories.payment_repository import PaymentRepositoryImp

logger = logging.getLogger(__name__)

# ── Firestore client ─────────────────────────────────────────────────────────

FirestoreClientDep = Annotated[AsyncClient, Depends(get_firestore_client)]

# ── Repositories ─────────────────────────────────────────────────────────────

async def get_otp_repo(db: FirestoreClientDep) -> OtpRepositoryImp:
    return OtpRepositoryImp(db=db)

OtpRepoDep = Annotated[OtpRepositoryImp, Depends(get_otp_repo)]

# ── SMS Client ───────────────────────────────────────────────────────────────

def get_sms_client() -> AfroMessageClient:
    return AfroMessageClient(
        api_key=MySettings.AFROMESSAGE_API_KEY,
        sender_name=MySettings.AFROMESSAGE_SENDER_NAME,
        identifier=MySettings.AFROMESSAGE_IDENTIFIER,
    )

SmsClientDep = Annotated[AfroMessageClient, Depends(get_sms_client)]

# ── Bearer token extraction ───────────────────────────────────────────────────
# auto_error=True → FastAPI returns 403 automatically if no Authorization header
_bearer_scheme = HTTPBearer(auto_error=True)


# ── Auth guard ────────────────────────────────────────────────────────────────

async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer_scheme)],
) -> dict[str, Any]:
    """Verify the Firebase ID token and return the decoded payload.

    The client must send:
        Authorization: Bearer <firebase-id-token>

    Returns a dict with at minimum:
        uid            — Firebase UID
        email          — user email (may be None if phone-only account)
        email_verified — bool

    Raises HTTP 401 for expired / invalid / revoked tokens.
    Raises HTTP 403 if the Authorization header is missing entirely.
    """
    token = credentials.credentials
    try:
        decoded = await verify_firebase_token(token)
    except firebase_auth.ExpiredIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase ID token has expired. Please re-authenticate.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except firebase_auth.RevokedIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase ID token has been revoked. Please re-authenticate.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except firebase_auth.InvalidIdTokenError as exc:
        logger.warning("Invalid Firebase ID token: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Firebase ID token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as exc:
        # Catch-all: never leak internal details to the client
        logger.error("Unexpected error during token verification: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return decoded


# Convenient type alias — use in route signatures:
#   user: CurrentUserDep
CurrentUserDep = Annotated[dict[str, Any], Depends(get_current_user)]


# ── Admin guard ───────────────────────────────────────────────────────────────

async def get_admin_user(
    user: CurrentUserDep,
) -> dict[str, Any]:
    """Require the `admin` custom claim to be set on the Firebase token.

    Set the claim server-side with:
        firebase_admin.auth.set_custom_user_claims(uid, {"admin": True})

    Raises HTTP 403 if the user is not an admin.
    """
    claims = user.get("admin", False)
    if not claims:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return user


AdminUserDep = Annotated[dict[str, Any], Depends(get_admin_user)]


# ── Chapa payment client ──────────────────────────────────────────────────────

def get_chapa_client() -> ChapaClient:
    """Return a configured ChapaClient.

    Raises HTTP 503 via ChapaNotConfiguredError if CHAPA_SECRET_KEY is missing.
    """
    from app.modules.payment.exceptions.exceptions import ChapaNotConfiguredError
    if not MySettings.CHAPA_SECRET_KEY:
        raise ChapaNotConfiguredError()
    return ChapaClient(
        secret_key=MySettings.CHAPA_SECRET_KEY,
        base_url=MySettings.CHAPA_BASE_URL,
    )


ChapaClientDep = Annotated[ChapaClient, Depends(get_chapa_client)]


# ── Payment repository ────────────────────────────────────────────────────────

async def get_payment_repo(db: FirestoreClientDep) -> PaymentRepositoryImp:
    """Return a PaymentRepositoryImp bound to the async Firestore client."""
    return PaymentRepositoryImp(
        db=db,
        plans_collection=MySettings.CHAPA_PLANS_COLLECTION,
    )


PaymentRepoDep = Annotated[PaymentRepositoryImp, Depends(get_payment_repo)]
