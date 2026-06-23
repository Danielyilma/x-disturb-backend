"""app/core/firebase.py — Firebase Admin SDK initialisation.

Replaces core/db.py from the SQLAlchemy blueprint.

Initialisation strategy (in order of precedence):
  1. FIREBASE_SERVICE_ACCOUNT_JSON env var  — inline JSON (preferred for Cloud Run)
  2. FIREBASE_SERVICE_ACCOUNT_KEY_PATH env var — path to a local JSON file (dev)
  3. Application Default Credentials (ADC) — used automatically on GCP

Exposes:
  - get_firestore_client()    — FastAPI dependency that returns an AsyncClient
  - get_storage_bucket()      — returns the Firebase Storage bucket handle
  - verify_firebase_token()   — async; verifies a Firebase ID token and returns
                                the decoded payload dict (uid, email, …)
"""

import asyncio
import json
import logging
from typing import Any

import firebase_admin
from firebase_admin import auth, credentials, firestore_async, storage
from google.cloud.firestore_v1.async_client import AsyncClient

from app.config import MySettings

logger = logging.getLogger(__name__)

_firebase_app: firebase_admin.App | None = None


def _init_firebase() -> firebase_admin.App:
    """Initialise the Firebase Admin SDK exactly once."""
    global _firebase_app  # noqa: PLW0603
    if _firebase_app is not None:
        return _firebase_app

    cred: credentials.Base

    if MySettings.FIREBASE_SERVICE_ACCOUNT_JSON:
        # Option A — inline JSON (Cloud Run / Secret Manager)
        account_info = json.loads(MySettings.FIREBASE_SERVICE_ACCOUNT_JSON)
        cred = credentials.Certificate(account_info)
        logger.info("Firebase initialised from inline JSON env var.")

    elif MySettings.FIREBASE_SERVICE_ACCOUNT_KEY_PATH:
        # Option B — local file path (dev)
        cred = credentials.Certificate(MySettings.FIREBASE_SERVICE_ACCOUNT_KEY_PATH)
        logger.info(
            "Firebase initialised from key file: %s",
            MySettings.FIREBASE_SERVICE_ACCOUNT_KEY_PATH,
        )

    else:
        # Option C — Application Default Credentials (GCP managed environments)
        cred = credentials.ApplicationDefault()
        logger.info("Firebase initialised using Application Default Credentials.")

    _firebase_app = firebase_admin.initialize_app(
        cred,
        options={
            "storageBucket": MySettings.FIREBASE_STORAGE_BUCKET,
            "projectId": MySettings.FIREBASE_PROJECT_ID,
        },
    )
    logger.info(
        "Firebase app initialised — project_id=%s storage_bucket=%s",
        MySettings.FIREBASE_PROJECT_ID or "(not set — check FIREBASE_PROJECT_ID)",
        MySettings.FIREBASE_STORAGE_BUCKET or "(not set — check FIREBASE_STORAGE_BUCKET)",
    )
    return _firebase_app


# Initialise at import time so the app fails fast if credentials are missing.
_init_firebase()


def get_firestore_client() -> AsyncClient:
    """Return an async Firestore client.

    Used as a FastAPI dependency:
        db: AsyncClient = Depends(get_firestore_client)

    The client is a singleton managed by the Firebase Admin SDK — it is
    thread-safe and connection-pooled internally.
    """
    return firestore_async.client()


def get_storage_bucket():
    """Return the Firebase Storage bucket handle.

    Used as a FastAPI dependency or called directly in service functions.
    """
    return storage.bucket()


async def verify_firebase_token(token: str) -> dict[str, Any]:
    """Verify a Firebase ID token and return its decoded payload.

    firebase_admin.auth.verify_id_token() is a blocking (synchronous) call.
    We run it in the default thread-pool executor so it never blocks the
    async event loop.

    Args:
        token: The raw Firebase ID token string from the Authorization header.

    Returns:
        Decoded token dict containing at minimum:
            uid   — Firebase UID (str)
            email — user's email address (str | None)
            email_verified — bool

    Raises:
        firebase_admin.auth.ExpiredIdTokenError  — token has expired
        firebase_admin.auth.InvalidIdTokenError  — token is malformed / invalid
        firebase_admin.auth.RevokedIdTokenError  — token has been revoked
        (all are subclasses of firebase_admin.auth.AuthError)
    """
    loop = asyncio.get_event_loop()
    # NOTE: check_revoked=False (default) — signature + expiry verified locally
    # using Google's public keys (no outbound credentials needed).
    # check_revoked=True would require an extra Google API call with service-account
    # credentials; enable it only when you can guarantee credentials are always
    # present (e.g., on Cloud Run with a bound service account).
    # TODO(security): Enable check_revoked=True in production once deployed on GCP.
    decoded: dict[str, Any] = await loop.run_in_executor(
        None,
        lambda: auth.verify_id_token(token),
    )
    return decoded
